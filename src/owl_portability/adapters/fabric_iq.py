"""Microsoft Fabric IQ adapter (simulation-first).

Fabric IQ currently depends on DirectLake-backed semantic stores for some graph
workloads; when Microsoft removes or replaces DirectLake, update the lakehouse
connection and IQ workspace endpoints here—OWL classes and SHACL stay stable.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from owl_portability.adapters.base import BaseAdapter

logger = logging.getLogger(__name__)


class FabricIQAdapter(BaseAdapter):
    """Simulated Fabric IQ entity create/query against workspace APIs."""

    def __init__(self, workspace_id: str, ontology_item_id: str, token: str) -> None:
        """Wire workspace, ontology artifact, and auth for IQ REST calls.

        Args:
            workspace_id: Fabric workspace identifier.
            ontology_item_id: IQ ontology item id backing entity types.
            token: Entra / Fabric token; optional for offline simulation.
        """
        self._workspace_id = workspace_id
        self._ontology_item_id = ontology_item_id
        self._token = token

    @property
    def platform_name(self) -> str:
        return "fabric_iq"

    def write(self, entity_data: dict[str, Any], entity_class: str) -> bool:
        url = (
            f"https://api.fabric.microsoft.com/v1/workspaces/{self._workspace_id}"
            f"/iq/ontologies/{self._ontology_item_id}/entities/simulation"
        )
        body = {"entityClass": entity_class, "payload": entity_data}
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.post(url, json=body, headers=headers)
            if r.status_code >= 500:
                logger.warning("Fabric IQ simulation POST returned %s", r.status_code)
            else:
                logger.info(
                    "Fabric IQ simulation write: class=%s status=%s",
                    entity_class,
                    r.status_code,
                )
        except httpx.HTTPError as exc:
            logger.info("Fabric IQ simulation write (offline): %s", exc)
        return True

    def read(self, entity_class: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        url = (
            f"https://api.fabric.microsoft.com/v1/workspaces/{self._workspace_id}"
            f"/iq/ontologies/{self._ontology_item_id}/entities/search"
        )
        params = {"class": entity_class, **filters}
        headers: dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(url, params=params, headers=headers)
            logger.info("Fabric IQ simulation read: status=%s", r.status_code)
        except httpx.HTTPError as exc:
            logger.info("Fabric IQ simulation read (offline): %s", exc)
        return []

    def health_check(self) -> bool:
        url = f"https://api.fabric.microsoft.com/v1/workspaces/{self._workspace_id}"
        headers: dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.get(url, headers=headers)
            return r.status_code < 500
        except httpx.HTTPError:
            return False
