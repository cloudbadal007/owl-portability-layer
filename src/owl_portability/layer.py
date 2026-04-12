"""Core OWL portability layer: SHACL validation with optional adapter routing."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyshacl
from rdflib import Graph

from owl_portability.adapters.base import BaseAdapter
from owl_portability.utils.rdf_builder import dict_to_entity_graph
from owl_portability.utils.shacl_reporter import violations_from_report

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Outcome of validating entity data against SHACL shapes.

    Attributes:
        passed: True when the data graph conforms to all shapes.
        violations: Human-readable constraint messages; empty when passed is True.
        platform_target: Intended downstream platform (empty for validate-only).
        entity_class: OWL class name validated (e.g. ``PaymentEvent``).
    """

    passed: bool
    violations: list[str] = field(default_factory=list)
    platform_target: str = ""
    entity_class: str = ""


class OWLPortabilityLayer:
    """Load ontology + SHACL, validate payloads, and route to registered adapters.

    Validation uses pyshacl with RDFS inference so subclass relationships in the
    ontology (e.g. ``ComplianceHold`` ⊑ ``HoldStatus``) are visible to shapes.
    """

    def __init__(self, ontology_path: str | Path, shacl_path: str | Path) -> None:
        """Load ontology and SHACL constraint graphs from Turtle files.

        Args:
            ontology_path: Path to the OWL ontology (``*.ttl``).
            shacl_path: Path to SHACL shapes (``*_shacl.ttl``).
        """
        self._ontology_path = Path(ontology_path)
        self._shacl_path = Path(shacl_path)
        self._ontology = Graph()
        self._shacl = Graph()
        self._ontology.parse(self._ontology_path.as_posix(), format="turtle")
        self._shacl.parse(self._shacl_path.as_posix(), format="turtle")
        self._adapters: dict[str, BaseAdapter] = {}

    def register_adapter(self, platform: str, adapter: BaseAdapter) -> None:
        """Register a platform adapter under a short key (e.g. ``palantir``, ``fabric_iq``).

        Args:
            platform: Key used in ``validate_and_route(..., target_platform=...)``.
            adapter: Concrete ``BaseAdapter`` implementation.
        """
        self._adapters[platform] = adapter

    def validate_only(self, entity_data: dict[str, Any], entity_class: str) -> ValidationResult:
        """Run SHACL validation without routing to any platform.

        Use for pre-flight checks and CI gates before writing to a live system.

        Args:
            entity_data: Key-value payload mapped to RDF by :mod:`owl_portability.utils.rdf_builder`.
            entity_class: Local OWL class name (e.g. ``PaymentEvent``, ``ComplianceHold``).

        Returns:
            ValidationResult with ``passed`` and ``violations`` populated.
        """
        return self._validate(entity_data, entity_class, platform_target="")

    def validate_and_route(
        self,
        entity_data: dict[str, Any],
        entity_class: str,
        target_platform: str,
    ) -> ValidationResult:
        """Validate against SHACL, then forward to the adapter for ``target_platform`` if valid.

        Args:
            entity_data: Business payload to lift into RDF and validate.
            entity_class: OWL class name for the focus resource.
            target_platform: Registered adapter key (must exist if validation passes).

        Returns:
            ValidationResult; on success, the adapter ``write`` is invoked.
        """
        result = self._validate(entity_data, entity_class, platform_target=target_platform)
        if not result.passed:
            return result
        adapter = self._adapters.get(target_platform)
        if adapter is None:
            msg = (
                f"No adapter registered for platform {target_platform!r}. "
                f"Registered keys: {sorted(self._adapters)}"
            )
            logger.error(msg)
            result.passed = False
            result.violations.append(msg)
            return result
        try:
            ok = adapter.write(entity_data, entity_class)
            if not ok:
                result.passed = False
                result.violations.append(
                    f"Adapter {target_platform!r} write() returned False."
                )
        except Exception as exc:  # noqa: BLE001 — surface adapter errors to callers
            logger.exception("Adapter write failed")
            result.passed = False
            result.violations.append(f"Adapter error: {exc}")
        return result

    def _validate(
        self,
        entity_data: dict[str, Any],
        entity_class: str,
        platform_target: str,
    ) -> ValidationResult:
        data_graph = dict_to_entity_graph(
            entity_data,
            entity_class,
            ontology_graph=self._ontology,
        )
        # Merge ontology for namespace consistency; pyshacl uses ont_graph for RDFS.
        merge = Graph()
        merge += self._ontology
        merge += data_graph
        try:
            conforms, report_graph, report_text = pyshacl.validate(
                merge,
                shacl_graph=self._shacl,
                ont_graph=self._ontology,
                inference="rdfs",
                abort_on_first=False,
                allow_infos=True,
                allow_warnings=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("SHACL validation failed to run")
            return ValidationResult(
                passed=False,
                violations=[f"Validation engine error: {exc}"],
                platform_target=platform_target,
                entity_class=entity_class,
            )
        violations = violations_from_report(report_graph, report_text)
        if conforms:
            return ValidationResult(
                passed=True,
                violations=[],
                platform_target=platform_target,
                entity_class=entity_class,
            )
        all_v = violations or ([report_text.strip()] if report_text else ["Unknown SHACL violation"])
        return ValidationResult(
            passed=False,
            violations=all_v,
            platform_target=platform_target,
            entity_class=entity_class,
        )
