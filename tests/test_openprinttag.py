"""Decoding check on the spec's sample tag; needs cbor2, pyyaml and a checkout of the spec.

    python tests/test_openprinttag.py <path to prusa3d/OpenPrintTag>
"""

from pathlib import Path
import sys

import yaml

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components" / "openprinttag"))
from openprinttag import Spec, decode, derive_uuids  # noqa: E402

data = Path(sys.argv[1]) / "data"
fields = {r: yaml.safe_load((data / f"{r}_fields.yaml").read_text()) for r in ("main", "aux")}
spec = Spec(fields, {})
spec = Spec(fields, {f: yaml.safe_load((data / f).read_text()) for f in spec.items_files()})

# The pn5180 host test's tag (spec sample + data_to_update.yaml): CC, TLV, NDEF header, MIME type, then the payload
mem = (Path(__file__).parent / "sample_tag.bin").read_bytes()
tag = decode(mem[42 : 42 + 261], spec)
main, aux = tag["main"], tag["aux"]
assert main["material_type"] == "PLA", main
assert main["material_class"] == "FFF"
assert main["material_name"] == "PLA Galaxy Black"
assert main["brand_name"] == "NOT Prusament"
assert main["primary_color"] == "#3d3e3d"
assert main["tags"] == ["glitter"]
assert main["manufactured_date"] == "2025-02-12T14:41:30+00:00"
assert main["instance_uuid"] == "473bb8cd-e129-45b8-9fcf-da1c3add9c47"
assert abs(main["transmission_distance"] - 0.2) < 0.001
assert aux == {"consumed_weight": 100}

# Derivation as in the spec's example and the database (Prusament PETG Jungle Green)
uuids = derive_uuids({"brand_name": "Prusament", "material_name": "PETG Jungle Green"}, "E0-04-01-08-66-2F-6F-BC")
assert uuids["brand_uuid"] == "ae5ff34e-298e-50c9-8f77-92a97fb30b09"
assert uuids["material_uuid"] == "481944dd-8319-5d9e-b4fa-d63d7da86f55"
assert uuids["instance_uuid"] == derive_uuids({}, "e0040108662f6fbc")["instance_uuid"]
print("ok")
