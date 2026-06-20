"""Abstract adapter contract for downstream ontology platforms."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAdapter(ABC):
    """Pluggable sink/source for validated entities.

    Implementations wrap vendor SDKs or HTTP APIs. The portability layer calls
    ``write`` only after SHACL validation succeeds, keeping policy enforcement
    centralized.
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Short stable name for logs and metrics (e.g. ``palantir_foundry``)."""

    @abstractmethod
    def write(self, entity_data: dict[str, Any], entity_class: str) -> bool:
        """Persist or enqueue one validated entity.

        Args:
            entity_data: Same dict passed to the portability layer.
            entity_class: OWL class local name.

        Returns:
            True if the operation succeeded from the adapter's perspective.
        """

    @abstractmethod
    def read(self, entity_class: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Query entities (simulated or live) for migration and reconciliation.

        Args:
            entity_class: OWL class to filter on.
            filters: Adapter-specific filter keys (IDs, date ranges, etc.).

        Returns:
            List of entity dicts in the same shape expected by ``write``.
        """

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if the remote endpoint or SDK session is usable."""
