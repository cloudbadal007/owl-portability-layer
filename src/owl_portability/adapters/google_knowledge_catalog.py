"""Google Knowledge Catalog adapter (simulation-first).

Part of the OntoArc enterprise ontology toolkit.
"""

from __future__ import annotations

from typing import Any

from owl_portability.adapters.base import BaseAdapter


class GoogleKnowledgeCatalogAdapter(BaseAdapter):
    """Simulated Google adapter for portability demos."""

    def __init__(self, project_id: str, simulation_mode: bool = True) -> None:
        """Set project context and simulation mode.

        Args:
            project_id: Google Cloud project id.
            simulation_mode: If True, print simulated operations only.
        """
        self._project_id = project_id
        self._simulation_mode = simulation_mode

    @property
    def platform_name(self) -> str:
        """Return platform identifier."""
        return "google_knowledge_catalog"

    def write(self, entity_data: dict[str, Any], entity_class: str) -> bool:
        """Simulate writing an entity."""
        if self._simulation_mode:
            print(
                f"[Google simulation] project={self._project_id} class={entity_class} payload={entity_data}"
            )
            return True
        return True

    def read(self, entity_class: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Simulate reading entities."""
        if self._simulation_mode:
            return [{"entity_class": entity_class, "source": "google", "simulation": True}]
        return []

    def health_check(self) -> bool:
        """Return adapter health status."""
        return True
