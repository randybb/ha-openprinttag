# OpenPrintTag for Home Assistant

Decodes [OpenPrintTag](https://openprinttag.org/) filament spool tags read by an
ESPHome reader (the `pn5180` component of
[randybb/esphome-components](https://github.com/randybb/esphome-components)) and
looks them up in the [OpenPrintTag database](https://github.com/OpenPrintTag/openprinttag-database).

Each reader gets a **Spool** sensor on its device:

* state: brand and material name (`Prusament PETG Jungle Green`), unknown without a tag
* picture: the material photo from the database
* attributes: every field of the tag by its spec name (main and aux region, enums
  as names, colors as `#rrggbb`, dates as ISO), the tag UID, the brand, material,
  package and instance UUIDs (derived as the spec says when the tag has none) and
  `database` with the brand, material and package records

Nothing is hardcoded: the field and enum tables come from the
[spec's](https://github.com/prusa3d/OpenPrintTag) `data/*.yaml`, the records from
the database's JSON API (`database.openprinttag.org/api`). Both are fetched on
first use and kept until HA restarts or the integration is reloaded.

## Installation

HACS custom repository `https://github.com/randybb/ha-openprinttag` (type
Integration), or copy `custom_components/openprinttag` to the HA config. Then
add the **OpenPrintTag** integration; there is nothing to configure.

## ESPHome reader

The reader sends the raw OpenPrintTag record as an event:

```yaml
pn5180:
  on_openprinttag:
    - homeassistant.event:
        event: esphome.openprinttag
        data:
          uid: !lambda return uid;
          payload: !lambda return payload;
  on_tag_removed:
    - homeassistant.event:
        event: esphome.openprinttag
        data:
          uid: !lambda return x;
          payload: ""
```

## Dashboard card

Built-in cards only; the entity IDs are those of a reader named `OpenPrintTag`:

```yaml
type: vertical-stack
cards:
  - type: markdown
    content: |
      {% set s = 'sensor.openprinttag_spool' %}
      {% if not has_value(s) %}
      No spool on the reader.
      {% else %}
      {% set a = states[s].attributes %}
      {% set full = a.actual_netto_full_weight | default(a.nominal_netto_full_weight) %}
      {% set length = a.actual_full_length | default(a.nominal_full_length) | default(0) %}
      {% set left = states('sensor.openprinttag_remaining_weight') | float(0) %}
      <img src="{{ a.entity_picture }}" width="110" align="right">

      ## {{ states(s) }}
      **{{ a.material_type }}** · {{ a.filament_diameter | default('–') }} mm · {{ a.primary_color | default('') }}

      | | |
      |---|---|
      | Print | {{ a.min_print_temperature | default('–') }}–{{ a.max_print_temperature | default('–') }} °C |
      | Bed | {{ a.min_bed_temperature | default('–') }}–{{ a.max_bed_temperature | default('–') }} °C |
      | Chamber | {{ a.chamber_temperature | default('–') }} °C |
      | Left | {{ left | round(0) }} g of {{ full }} g{% if length and full %} · ~{{ (length * left / full / 1000) | round(0) }} m{% endif %} |
      | Made | {{ as_datetime(a.manufactured_date).date() if a.manufactured_date is defined else '–' }} |
      {% endif %}
  - type: tile
    entity: light.openprinttag_filament_color
```

`sensor.openprinttag_remaining_weight` and `light.openprinttag_filament_color`
come from the reader's ESPHome config (`pn5180` sensor, an `rgb` light fed by the
`primary_color` text sensor), see `mcu-rfid-openprinttag.yaml` in the reader's
config.

## Testing

The decoder has no HA imports and is checked on the spec's sample tag:

```sh
pip install cbor2 pyyaml
git clone https://github.com/prusa3d/OpenPrintTag /tmp/OpenPrintTag
python tests/test_openprinttag.py /tmp/OpenPrintTag
```
