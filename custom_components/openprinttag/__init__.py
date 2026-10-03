"""OpenPrintTag: spools read by ESPHome readers, decoded and looked up in the OpenPrintTag database."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .data import OpenPrintTagData

PLATFORMS = [Platform.SENSOR]

type OpenPrintTagConfigEntry = ConfigEntry[OpenPrintTagData]


async def async_setup_entry(hass: HomeAssistant, entry: OpenPrintTagConfigEntry) -> bool:
    entry.runtime_data = OpenPrintTagData(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenPrintTagConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
