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
  `database` with the brand, material and package records, and `on_reader`
  (when the tag is removed the state goes unknown, the attributes stay with
  `on_reader: false`)

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

## Updating the tag

`openprinttag.update` writes values to the aux region of the tag on the reader,
keeping every other field (unknown ones too); only the changed blocks are
written, then the reader reads the tag again and the sensor shows what is on it.

```yaml
action: openprinttag.update
target:
  entity_id: sensor.openprinttag_spool
data:
  consume: 23.5          # used by a print, added to consumed_weight
  # consumed_weight: 250 # or set it
  # gross_weight: 812    # or weigh the spool with its container
  storage_location: Shelf A  # empty text removes it
```

The reader needs an API action for it:

```yaml
api:
  actions:
    - action: openprinttag_write_aux
      variables:
        uid: string
        aux: string
      then:
        - lambda: id(pn5180_reader).write_aux(uid, aux);
```

The fields, all optional, can be combined in one call:

| Field | Writes |
|---|---|
| `consumed_weight` | the consumed weight, g |
| `consume` | adds to the consumed weight, g (negative takes back) |
| `gross_weight` | the consumed weight from the spool weighed with its container: full weight + empty container weight − `gross_weight` (both weights from the tag) |
| `storage_location` | where the spool is kept, empty text removes it |
| `workgroup` | who the spool belongs to, empty text removes it |

The spool has to be on the reader: the action fails when its tag is not there.
The sensor shows the new values a moment later, once the reader has read the
tag back.

### From a dashboard

**Developer tools → Actions** runs it by hand. On a dashboard, a button with a
fixed value:

```yaml
type: button
name: Used 10 g
icon: mdi:minus-circle-outline
tap_action:
  action: perform-action
  perform_action: openprinttag.update
  target:
    entity_id: sensor.openprinttag_spool
  data:
    consume: 10
```

For a value typed in (e.g. the spool on a kitchen scale), a number helper, a
script that writes it and both on a dashboard; dashboard actions do not take
templates, the script does. Create the helper in **Settings → Devices &
services → Helpers → Number** (here `input_number.spool_weight`, 0–5000 g,
display mode input field), then the script:

```yaml
# scripts.yaml
openprinttag_weigh:
  alias: Write the weighed spool to the tag
  icon: mdi:scale
  sequence:
    - action: openprinttag.update
      target:
        entity_id: sensor.openprinttag_spool
      data:
        gross_weight: "{{ states('input_number.spool_weight') | float }}"
```

```yaml
type: entities
title: Weigh the spool
entities:
  - entity: input_number.spool_weight
    name: Weight with the container
  - entity: script.openprinttag_weigh
    name: Write to the tag
```

Set `consumed_weight` or `consume` in the script instead for those.

### From an automation

E.g. the filament a print used, from a printer integration:

```yaml
actions:
  - action: openprinttag.update
    target:
      entity_id: sensor.openprinttag_spool
    data:
      consume: "{{ states('sensor.printer_filament_used') | float(0) }}"
```

## Dashboard card

The integration brings its own card, nothing to install: in a dashboard,
**Add card → OpenPrintTag Spool** and pick the reader's Spool sensor.

```yaml
type: custom:openprinttag-card
entity: sensor.openprinttag_spool
sticky: true  # keep showing the last spool, dimmed, after its tag is removed
```

It shows the filament color, the material photo, the remaining filament
(full weight minus `consumed_weight` from the tag, and the length from it),
the temperatures and the tag's tags and certifications.

## Testing

The decoder has no HA imports and is checked on the spec's sample tag:

```sh
pip install cbor2 pyyaml
git clone https://github.com/prusa3d/OpenPrintTag /tmp/OpenPrintTag
python tests/test_openprinttag.py /tmp/OpenPrintTag
```
