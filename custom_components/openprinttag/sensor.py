"""A spool sensor on each ESPHome reader's device, fed by the esphome.openprinttag event."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import OpenPrintTagConfigEntry
from .const import EVENT
from .openprinttag import decode, derive_uuids

_LOGGER = logging.getLogger(__name__)

# State attributes HA sets itself, not restored as tag data
_OWN_ATTRIBUTES = {"friendly_name", "icon", "entity_picture"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenPrintTagConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    data = entry.runtime_data
    entities: dict[str, SpoolSensor] = {}

    @callback
    def add(device_id: str) -> SpoolSensor | None:
        device = dr.async_get(hass).async_get(device_id)
        if device is None:
            return None
        entity = entities[device_id] = SpoolSensor(device)
        async_add_entities([entity])
        return entity

    # Readers seen before get their sensor back right away, with the restored state
    for reg in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id):
        add(reg.unique_id)

    async def handle(event: Event) -> None:
        device_id = event.data.get("device_id")
        entity = entities.get(device_id) or add(device_id) if device_id else None
        if entity is None:
            return
        uid = event.data.get("uid", "")
        payload = event.data.get("payload", "")
        if not payload:  # tag removed
            entity.set_tag(None)
            return
        try:
            tag = decode(bytes.fromhex(payload), await data.spec())
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Could not load the OpenPrintTag spec: %s", err)
            return
        except ValueError as err:
            _LOGGER.warning("Undecodable OpenPrintTag %s: %s", uid, err)
            return
        uuids = derive_uuids(tag["main"], uid)
        db = await data.lookup(uuids, tag["main"])
        entity.set_tag({"uid": uid, **uuids, **tag["main"], **tag["aux"]}, db)

    entry.async_on_unload(hass.bus.async_listen(EVENT, handle))


class SpoolSensor(SensorEntity, RestoreEntity):
    """The spool on the reader: brand and material name, all tag fields and the database record.

    When the tag is removed the state goes unknown but the attributes stay, with
    on_reader false, so a dashboard can keep showing the last spool.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "spool"
    _attr_icon = "mdi:printer-3d-nozzle"
    _attr_should_poll = False

    def __init__(self, device: dr.DeviceEntry) -> None:
        self._attr_unique_id = device.id
        self._attr_device_info = DeviceInfo(identifiers=device.identifiers, connections=device.connections)
        self._got_event = False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if self._got_event or last is None or last.state == STATE_UNAVAILABLE:
            return
        self._attr_native_value = None if last.state == STATE_UNKNOWN else last.state
        self._attr_entity_picture = last.attributes.get("entity_picture")
        self._attr_extra_state_attributes = {k: v for k, v in last.attributes.items() if k not in _OWN_ATTRIBUTES}

    @callback
    def set_tag(self, tag: dict[str, Any] | None, db: dict[str, Any] | None = None) -> None:
        self._got_event = True
        if tag is None:
            self._attr_native_value = None
            if self._attr_extra_state_attributes:
                self._attr_extra_state_attributes = {**self._attr_extra_state_attributes, "on_reader": False}
        else:
            photos = (db or {}).get("material", {}).get("photos") or []
            name = " ".join(str(tag[k]) for k in ("brand_name", "material_name") if k in tag)
            self._attr_native_value = name or tag["uid"]
            self._attr_entity_picture = photos[0].get("url") if photos else None
            self._attr_extra_state_attributes = {**tag, "database": db or {}, "on_reader": True}
        if self.hass is not None:  # not yet added: HA writes the state when it is
            self.async_write_ha_state()
