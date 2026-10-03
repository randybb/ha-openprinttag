"""OpenPrintTag: spools read by ESPHome readers, decoded and looked up in the OpenPrintTag database."""

from __future__ import annotations

import hashlib
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, UPDATE_SCHEMA
from .data import OpenPrintTagData

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
CARD = Path(__file__).parent / "frontend" / "openprinttag-card.js"
CARD_URL = f"/{DOMAIN}/openprinttag-card.js"

type OpenPrintTagConfigEntry = ConfigEntry[OpenPrintTagData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the dashboard card and load it on every dashboard."""
    version = await hass.async_add_executor_job(lambda: hashlib.md5(CARD.read_bytes()).hexdigest()[:8])
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(CARD), False)])
    url = f"{CARD_URL}?v={version}"  # the hash busts the browser cache on updates
    if not await _add_lovelace_resource(hass, url):
        add_extra_js_url(hass, url)
    service.async_register_platform_entity_service(
        hass, DOMAIN, "update", entity_domain=SENSOR_DOMAIN, schema=UPDATE_SCHEMA, func="async_update_tag"
    )
    return True


async def _add_lovelace_resource(hass: HomeAssistant, url: str) -> bool:
    """Add or update the card in the dashboard resources, as HACS does for cards.

    The resources come with the dashboard config, an extra JS URL comes with the
    page HTML, which a browser can keep stale. False in YAML resource mode.
    """
    resources = hass.data[LOVELACE_DATA].resources
    if not isinstance(resources, ResourceStorageCollection):
        return False
    await resources.async_get_info()  # loads the collection
    for item in resources.async_items():
        if item["url"].split("?")[0] == CARD_URL:
            if item["url"] != url:
                await resources.async_update_item(item["id"], {"res_type": "module", "url": url})
            return True
    await resources.async_create_item({"res_type": "module", "url": url})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OpenPrintTagConfigEntry) -> bool:
    entry.runtime_data = OpenPrintTagData(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenPrintTagConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
