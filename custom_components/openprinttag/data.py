"""Spec tables and OpenPrintTag database lookups, fetched once and kept for the HA run."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp
import yaml

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .openprinttag import Spec

_LOGGER = logging.getLogger(__name__)

SPEC_URL = "https://raw.githubusercontent.com/prusa3d/OpenPrintTag/main/data/"
DB_URL = "https://database.openprinttag.org/api/"
TIMEOUT = aiohttp.ClientTimeout(total=30)


class OpenPrintTagData:
    """Downloads the spec and database files on first use.

    ponytail: cached until HA restarts, a reload of the integration picks up database changes.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._session = async_get_clientsession(hass)
        self._cache: dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._spec: Spec | None = None

    async def _get(self, url: str) -> Any:
        if url not in self._cache:
            async with self._session.get(url, timeout=TIMEOUT) as resp:
                resp.raise_for_status()
                text = await resp.text()
            parse = json.loads if url.endswith(".json") else yaml.safe_load
            self._cache[url] = await self._hass.async_add_executor_job(parse, text)
        return self._cache[url]

    async def spec(self) -> Spec:
        async with self._lock:
            if self._spec is None:
                fields = {r: await self._get(f"{SPEC_URL}{r}_fields.yaml") for r in ("main", "aux")}
                files = Spec(fields, {}).items_files()
                self._spec = Spec(fields, {f: await self._get(SPEC_URL + f) for f in files})
            return self._spec

    async def lookup(self, uuids: dict[str, str], main: dict[str, Any]) -> dict[str, Any]:
        """Brand, material and package records of the tag, those the database has."""
        out: dict[str, Any] = {}
        try:
            brands = await self._get(f"{DB_URL}brands/basic.json")
            brand = next((b for b in brands if b.get("uuid") == uuids.get("brand_uuid")), None)
            if brand is None:
                return out
            out["brand"] = brand
            base = f"{DB_URL}brands/{brand['slug']}/"
            materials = await self._get(base + "materials.json")
            material = next((m for m in materials if m.get("uuid") == uuids.get("material_uuid")), None)
            if material is not None:
                out["material"] = material
            packages = await self._get(base + "packages.json")
            gtin = main.get("gtin")
            candidates = [
                p
                for p in packages
                if p.get("uuid") == uuids.get("package_uuid") or (gtin is not None and p.get("gtin") == gtin)
            ]
            if len(candidates) > 1:
                # Packages can share a GTIN (a spool and its older design): the spool the tag
                # describes wins, then the UUID derived from the tag
                containers = {c.get("slug"): c for c in await self._get(f"{DB_URL}containers.json")}

                def mismatch(p: dict[str, Any]) -> tuple[int, bool]:
                    c = containers.get((p.get("container") or {}).get("slug"), {})
                    pairs = (("empty_container_weight", "empty_weight"), ("container_width", "width"))
                    return (
                        sum(k in main and c.get(ck) != main[k] for k, ck in pairs),
                        p.get("uuid") != uuids.get("package_uuid"),
                    )

                candidates.sort(key=mismatch)
            if candidates:
                out["package"] = candidates[0]
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.warning("OpenPrintTag database lookup failed: %s", err)
        return out
