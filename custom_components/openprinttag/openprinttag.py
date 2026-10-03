"""OpenPrintTag payload decoding and UUID derivation, without Home Assistant imports."""

from __future__ import annotations

from datetime import UTC, datetime
import io
from typing import Any
import uuid

import cbor2

# UUIDv5 namespaces from the OpenPrintTag spec (nfc_data_format, "UUIDs")
NAMESPACE_BRAND = uuid.UUID("5269dfb7-1559-440a-85be-aba5f3eff2d2")
NAMESPACE_MATERIAL = uuid.UUID("616fc86d-7d99-4953-96c7-46d2836b9be9")
NAMESPACE_PACKAGE = uuid.UUID("6f7d485e-db8d-4979-904e-a231cd6602b2")
NAMESPACE_INSTANCE = uuid.UUID("31062f81-b5bd-4f86-a5f8-46367e841508")


class Spec:
    """Field and enum tables of the spec, as loaded from its data/*.yaml files.

    fields: region ("main", "aux") -> list of field entries (key, name, type, items_file, ...)
    enums: items_file -> list of enum items (key, name, ...)
    """

    def __init__(self, fields: dict[str, list[dict]], enums: dict[str, list[dict]]) -> None:
        self.fields = {
            region: {f["key"]: f for f in entries if "name" in f} for region, entries in fields.items()
        }
        self.enums = {name: {i["key"]: i for i in items} for name, items in enums.items()}

    def items_files(self) -> set[str]:
        return {f["items_file"] for r in self.fields.values() for f in r.values() if "items_file" in f}


def _convert(field: dict | None, value: Any, spec: Spec) -> Any:
    kind = field.get("type") if field else None
    if kind == "uuid" and isinstance(value, bytes) and len(value) == 16:
        return str(uuid.UUID(bytes=value))
    if kind == "color_rgba" and isinstance(value, bytes):
        # an opaque alpha is dropped so the value is a plain #rrggbb
        return "#" + (value[:3] if value[3:] == b"\xff" else value).hex()
    if kind == "timestamp" and isinstance(value, int):
        return datetime.fromtimestamp(value, UTC).isoformat()
    if kind in ("enum", "enum_array"):
        items = spec.enums.get(field.get("items_file", ""), {})
        name = field.get("name_field", "name")

        def item(key: Any) -> Any:
            return items[key].get(name, key) if key in items else key

        return [item(k) for k in value] if isinstance(value, list) else item(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


def _region(payload: bytes, offset: int, region: str, spec: Spec) -> dict[str, Any]:
    data = cbor2.CBORDecoder(io.BytesIO(payload[offset:])).decode()
    if not isinstance(data, dict):
        raise ValueError(f"{region} region is not a map")
    out = {}
    for key, value in data.items():
        field = spec.fields.get(region, {}).get(key)
        out[field["name"] if field else str(key)] = _convert(field, value, spec)
    return out


def decode(payload: bytes, spec: Spec) -> dict[str, dict[str, Any]]:
    """Decode the application/vnd.openprinttag NDEF payload into named main and aux fields."""
    stream = io.BytesIO(payload)
    meta = cbor2.CBORDecoder(stream).decode()
    if not isinstance(meta, dict):
        raise ValueError("meta section is not a map")
    result = {"main": _region(payload, meta.get(0, stream.tell()), "main", spec), "aux": {}}
    if 2 in meta:
        try:
            result["aux"] = _region(payload, meta[2], "aux", spec)
        except (cbor2.CBORDecodeError, ValueError):
            pass  # a blank aux region is not an error
    return result


def derive_uuids(main: dict[str, Any], tag_uid: str) -> dict[str, str]:
    """UUIDs of the tag, derived as the spec says when the tag does not carry them."""
    out = {}
    brand = main.get("brand_uuid")
    if brand is None and "brand_name" in main:
        brand = str(uuid.uuid5(NAMESPACE_BRAND, main["brand_name"].encode()))
    if brand is not None:
        out["brand_uuid"] = brand
        brand_bytes = uuid.UUID(brand).bytes
        if "material_uuid" in main:
            out["material_uuid"] = main["material_uuid"]
        elif "material_name" in main:
            out["material_uuid"] = str(uuid.uuid5(NAMESPACE_MATERIAL, brand_bytes + main["material_name"].encode()))
        if "package_uuid" in main:
            out["package_uuid"] = main["package_uuid"]
        elif "gtin" in main:
            out["package_uuid"] = str(uuid.uuid5(NAMESPACE_PACKAGE, brand_bytes + str(main["gtin"]).encode()))
    if "instance_uuid" in main:
        out["instance_uuid"] = main["instance_uuid"]
    elif tag_uid:
        # the reader sends E0-04-..., the MSB (0xE0) first as the spec wants
        out["instance_uuid"] = str(uuid.uuid5(NAMESPACE_INSTANCE, bytes.fromhex(tag_uid.replace("-", ""))))
    return out
