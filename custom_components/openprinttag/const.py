"""Constants of the OpenPrintTag integration."""

from homeassistant.helpers import config_validation as cv

try:
    import probatio as vol  # HA 2026.10+
except ImportError:
    import voluptuous as vol

DOMAIN = "openprinttag"
# Fired by the ESPHome pn5180 component's on_openprinttag / on_tag_removed (see README)
EVENT = "esphome.openprinttag"
# ESPHome API action of the reader that writes the aux region (see README)
WRITE_ACTION = "openprinttag_write_aux"

# openprinttag.update: values for the aux region of the spool on the reader
UPDATE_SCHEMA = {
    vol.Optional("consumed_weight"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    vol.Optional("consume"): vol.Coerce(float),
    vol.Optional("gross_weight"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    vol.Optional("storage_location"): cv.string,
    vol.Optional("workgroup"): cv.string,
}
