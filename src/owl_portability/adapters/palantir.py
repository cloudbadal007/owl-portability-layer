"""Palantir Foundry OSDK-style adapter (simulation-first; swap in real OSDK)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from owl_portability.adapters.base import BaseAdapter

logger = logging.getLogger(__name__)


class PalantirFoundryAdapter(BaseAdapter):
    """Simulated Foundry object writes/queries.

    Replace simulation methods with real OSDK calls. When you leave Palantir,
    delete this file. Nothing else changes.

    ``object_type_map`` maps OWL class names (``PaymentEvent``) to Foundry
    Object Type RIDs so a single semantic model can drive heterogeneous types.
    """

    def __init__(
        self,
        foundry_url: str,
        token: str,
        object_type_map: dict[str, str],
    ) -> None:
        """Configure base URL, bearer token, and OWL→Object Type mapping.

        Args:
            foundry_url: Foundry stack base URL (e.g. ``https://example.palantirfoundry.com``).
            token: OAuth bearer token; may be empty when running in simulation.
            object_type_map: Maps ``entity_class`` strings to Palantir object type identifiers.
        """
        self._foundry_url = foundry_url.rstrip("/")
        self._token = token
        self._object_type_map = object_type_map

    @property
    def platform_name(self) -> str:
        return "palantir_foundry"

    def write(self, entity_data: dict[str, Any], entity_class: str) -> bool:
        object_rid = self._object_type_map.get(entity_class)
        if not object_rid:
            logger.error("No Object Type mapping for OWL class %s", entity_class)
            return False
        payload = {"objectTypeRid": object_rid, "properties": entity_data}
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        url = f"{self._foundry_url}/api/simulation/osdk/objects"
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.post(url, json=payload, headers=headers)
            # Simulation: accept 404/connection errors as success so demos run offline.
            if r.status_code >= 500:
                logger.warning("Foundry simulation POST returned %s", r.status_code)
            else:
                logger.info(
                    "Palantir simulation write: class=%s status=%s",
                    entity_class,
                    r.status_code,
                )
        except httpx.HTTPError as exc:
            logger.info("Palantir simulation write (offline): %s", exc)
        return True

    def read(self, entity_class: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        object_rid = self._object_type_map.get(entity_class, "unknown-rid")
        params = {"objectTypeRid": object_rid, **filters}
        url = f"{self._foundry_url}/api/simulation/osdk/objects/search"
        headers: dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(url, params=params, headers=headers)
            logger.info("Palantir simulation read: status=%s", r.status_code)
        except httpx.HTTPError as exc:
            logger.info("Palantir simulation read (offline): %s", exc)
        return []

    def health_check(self) -> bool:
        url = f"{self._foundry_url}/health"
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.get(url)
            return r.status_code < 500
        except httpx.HTTPError:
            return False
