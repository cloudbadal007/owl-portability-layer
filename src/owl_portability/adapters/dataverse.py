"""Microsoft Dataverse Agent Data Platform Semantic Adapter.

Dataverse's intelligent semantic layer gives agents business understanding —
schema graph traversal, Business Skills, procedural knowledge from workflows.
OWL/SHACL gives agents formal constraint enforcement — what agents are
permitted to DO with that understanding. Microsoft ships the first. This
adapter adds the second.

Dataverse: semantic layer for operational agents (Dynamics 365, Power Apps,
M365 — already deployed at scale). Fabric IQ: semantic layer for analytics
agents (DirectLake, OneLake — requires Fabric migration). Both coexist in
Microsoft's agentic stack.

When you leave Microsoft Dataverse, delete this file. Your OWL ontology and
SHACL constraints remain unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pyshacl
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

from owl_portability.adapters.base import BaseAdapter
from owl_portability.utils.shacl_reporter import violations_from_report

logger = logging.getLogger(__name__)

PROC = Namespace("http://enterprise.org/procurement#")

_HTTPX_AVAILABLE = False
_httpx: Any = None
try:
    import httpx as _httpx_module

    _httpx = _httpx_module
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

@dataclass
class DataverseAgentQuery:
    """Inbound Dataverse agent action with semantic grounding context."""

    query_id: str
    agent_id: str
    action_type: str
    entity_class: str
    payload: dict[str, Any]
    dataverse_context: dict[str, Any]
    skill_applied: str | None = None

@dataclass
class DataverseValidationResult:
    """Outcome of two-layer validation: Dataverse grounding plus OWL/SHACL."""

    query_id: str
    agent_id: str
    action_type: str
    dataverse_grounded: bool
    shacl_valid: bool
    violations: list[str] = field(default_factory=list)
    safe_to_execute: bool = False

    def __post_init__(self) -> None:
        """Both layers must pass — understanding AND governance."""
        self.safe_to_execute = self.dataverse_grounded and self.shacl_valid

class DataverseSemanticAdapter(BaseAdapter):
    """Bridge Dataverse semantic grounding with OWL/SHACL domain validation.

    Dataverse Semantic Layer (Microsoft):
      Understands: schema, relationships, business rules, skills
      Cannot enforce: formal OWL class constraints, SHACL rules

    OWL/SHACL Layer (This Adapter):
      Enforces: domain constraints, hold type hierarchy,
                approval requirements, value thresholds
      Cannot provide: schema-aware retrieval, skill context

    Both are necessary. Microsoft ships the first.
    Build the second.
    """

    DATAVERSE_TO_OWL_MAP: dict[str, str] = {
        "cr9a1_paymentevent": "PaymentEvent",
        "cr9a1_compliancehold": "ComplianceHold",
        "cr9a1_budgethold": "BudgetHold",
        "cr9a1_vendordispute": "VendorDisputeHold",
        "cr9a1_contract": "Contract",
        "cr9a1_vendor": "Vendor",
        "account": "Vendor",
        "opportunity": "Contract",
        "invoice": "PaymentEvent",
        "salesorder": "Contract",
    }

    DATAVERSE_FIELD_MAP: dict[str, str] = {
        "cr9a1_amountusd": "amountUSD",
        "cr9a1_holdtype": "hasHoldStatus",
        "cr9a1_approvedby": "holdApprovedBy",
        "cr9a1_paymentid": "paymentId",
        "amount": "amountUSD",
        "holdType": "hasHoldStatus",
        "approvedBy": "holdApprovedBy",
        "paymentId": "paymentId",
        "totalamount": "amountUSD",
        "cr9a1_contractval": "contractValue",
    }

    def __init__(
        self,
        ontology_path: str,
        shacl_path: str,
        dataverse_url: str = "",
        access_token: str = "",
        simulation_mode: bool = True,
    ) -> None:
        """Load ontology and SHACL graphs; configure Dataverse API access.

        Args:
            ontology_path: Path to OWL ontology Turtle file.
            shacl_path: Path to SHACL shapes Turtle file.
            dataverse_url: Dataverse environment URL (e.g. https://yourorg.crm.dynamics.com).
            access_token: OAuth token for Dataverse Web API.
            simulation_mode: When True, skip live API calls (default).
        """
        self._dataverse_url = dataverse_url.rstrip("/")
        self._access_token = access_token
        self._simulation_mode = simulation_mode
        self._ontology = Graph()
        self._shacl = Graph()
        self._ontology.parse(Path(ontology_path).as_posix(), format="turtle")
        self._shacl.parse(Path(shacl_path).as_posix(), format="turtle")

    @property
    def platform_name(self) -> str:
        """Return stable adapter platform identifier."""
        return "microsoft_dataverse"

    def validate_dataverse_action(
        self, query: DataverseAgentQuery
    ) -> DataverseValidationResult:
        """Validate a Dataverse agent action against semantic grounding and SHACL.

        Args:
            query: Agent action with payload and Dataverse semantic context.

        Returns:
            DataverseValidationResult with grounding, SHACL, and safe_to_execute flags.
        """
        base = DataverseValidationResult(
            query_id=query.query_id,
            agent_id=query.agent_id,
            action_type=query.action_type,
            dataverse_grounded=False,
            shacl_valid=False,
        )

        if not query.dataverse_context:
            base.violations = [
                "Dataverse semantic layer returned no context. "
                "Agent grounding failed. Execution blocked."
            ]
            return self._finalize_result(base)

        base.dataverse_grounded = True
        owl_class = self.DATAVERSE_TO_OWL_MAP.get(query.entity_class, query.entity_class)
        data_graph = self._build_entity_rdf(query, owl_class)
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
            base.violations = [f"Validation engine error: {exc}"]
            return self._finalize_result(base)

        if conforms:
            base.shacl_valid = True
            return self._finalize_result(base)

        violations = violations_from_report(report_graph, report_text)
        if not violations and report_text:
            violations = [report_text.strip()]
        violations = self._enrich_compliance_hold_violations(query, violations)
        base.violations = violations
        return self._finalize_result(base)

    @staticmethod
    def _finalize_result(result: DataverseValidationResult) -> DataverseValidationResult:
        """Recompute safe_to_execute after mutating grounding or SHACL flags."""
        result.safe_to_execute = result.dataverse_grounded and result.shacl_valid
        return result

    def _enrich_compliance_hold_violations(
        self,
        query: DataverseAgentQuery,
        violations: list[str],
    ) -> list[str]:
        """Add domain-friendly Legal approval message when ComplianceHold lacks approver."""
        hold_type = (
            query.payload.get("cr9a1_holdtype")
            or query.payload.get("holdType")
            or ""
        )
        approved_by = (
            query.payload.get("cr9a1_approvedby")
            or query.payload.get("approvedBy")
        )
        if hold_type == "ComplianceHold" and not approved_by:
            friendly = "ComplianceHold requires Legal approval before release."
            if not any("Legal approval" in v for v in violations):
                violations = list(violations) + [friendly]
        return violations

    def _build_entity_rdf(self, query: DataverseAgentQuery, owl_class: str) -> Graph:
        """Map Dataverse payload fields to procurement ontology triples.

        Args:
            query: Agent query with Dataverse field names in payload.
            owl_class: OWL class local name from DATAVERSE_TO_OWL_MAP.

        Returns:
            RDF graph for the entity and nested hold nodes.
        """
        g = Graph()
        root = URIRef(
            f"http://enterprise.org/procurement/instance/{owl_class}/{query.query_id}"
        )
        g.add((root, RDF.type, PROC[owl_class]))

        mapped: dict[str, Any] = {}
        hold_value: str | None = None
        for key, value in query.payload.items():
            owl_prop = self.DATAVERSE_FIELD_MAP.get(key)
            if owl_prop is None:
                continue
            if owl_prop == "hasHoldStatus":
                hold_value = str(value)
            else:
                mapped[owl_prop] = value

        if "amountUSD" in mapped:
            g.add(
                (
                    root,
                    PROC.amountUSD,
                    Literal(Decimal(str(mapped["amountUSD"])), datatype=XSD.decimal),
                )
            )
        if "paymentId" in mapped:
            g.add(
                (
                    root,
                    PROC.paymentId,
                    Literal(str(mapped["paymentId"]), datatype=XSD.string),
                )
            )
        if "contractValue" in mapped:
            g.add(
                (
                    root,
                    PROC.contractValue,
                    Literal(Decimal(str(mapped["contractValue"])), datatype=XSD.decimal),
                )
            )

        if hold_value:
            hold_node: URIRef | BNode = URIRef(
                f"http://enterprise.org/procurement/instance/{hold_value}/{query.query_id}"
            )
            g.add((hold_node, RDF.type, PROC[hold_value]))
            g.add((root, PROC.hasHoldStatus, hold_node))
            approved_by = mapped.get("holdApprovedBy")
            if approved_by:
                approver = Literal(str(approved_by), datatype=XSD.string)
                g.add((hold_node, PROC.holdApprovedBy, approver))
                g.add((root, PROC.holdApprovedBy, approver))
        elif "holdApprovedBy" in mapped:
            g.add(
                (
                    root,
                    PROC.holdApprovedBy,
                    Literal(str(mapped["holdApprovedBy"]), datatype=XSD.string),
                )
            )

        return g

    def _owl_to_dataverse_table(self, entity_class: str) -> str:
        """Resolve OWL class name to a Dataverse table logical name."""
        for dv_name, owl_name in self.DATAVERSE_TO_OWL_MAP.items():
            if owl_name == entity_class:
                return dv_name
        return entity_class

    def _auth_headers(self) -> dict[str, str]:
        """Build HTTP headers for Dataverse Web API calls."""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def write(self, entity_data: dict[str, Any], entity_class: str) -> bool:
        """Persist a validated entity to Dataverse (simulated or live).

        Args:
            entity_data: Validated business payload.
            entity_class: OWL class local name.

        Returns:
            True on success.
        """
        table_name = self._owl_to_dataverse_table(entity_class)

        if self._simulation_mode:
            print(f"[Dataverse simulation] write entity_class={entity_class} table={table_name}")
            print(f"  entity_data={entity_data}")
            return True

        if not _HTTPX_AVAILABLE:
            print(
                "httpx is not installed. Install httpx>=0.27.0 for production "
                "Dataverse writes."
            )
            return False

        url = f"{self._dataverse_url}/api/data/v9.2/{table_name}s"
        try:
            with _httpx.Client(timeout=10.0) as client:
                response = client.post(url, json=entity_data, headers=self._auth_headers())
            return response.status_code in (200, 201, 204)
        except Exception as exc:  # noqa: BLE001
            print(f"Dataverse write failed for {entity_class}: {exc}")
            return False

    def read(self, entity_class: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Query Dataverse entities (simulated or live).

        Args:
            entity_class: OWL class to filter on.
            filters: Field filters converted to OData expressions in production mode.

        Returns:
            Matching entity dicts, or simulation placeholder.
        """
        table_name = self._owl_to_dataverse_table(entity_class)

        if self._simulation_mode:
            return [
                {
                    "entity_class": entity_class,
                    "source": "dataverse",
                    "simulation": True,
                    "filters": filters,
                }
            ]

        if not _HTTPX_AVAILABLE:
            print(
                "httpx is not installed. Install httpx>=0.27.0 for production "
                "Dataverse reads."
            )
            return []

        filter_parts = [
            f"{quote(str(k), safe='')} eq '{v}'" for k, v in filters.items()
        ]
        params: dict[str, str] = {}
        if filter_parts:
            params["$filter"] = " and ".join(filter_parts)

        url = f"{self._dataverse_url}/api/data/v9.2/{table_name}s"
        try:
            with _httpx.Client(timeout=10.0) as client:
                response = client.get(url, params=params, headers=self._auth_headers())
            if response.status_code != 200:
                return []
            body = response.json()
            return body.get("value", [])
        except Exception as exc:  # noqa: BLE001
            print(f"Dataverse read failed for {entity_class}: {exc}")
            return []

    def health_check(self) -> bool:
        """Return True if the Dataverse environment is reachable."""
        if self._simulation_mode:
            return True

        if not _HTTPX_AVAILABLE:
            print(
                "httpx is not installed. Install httpx>=0.27.0 for production "
                "Dataverse health checks."
            )
            return False

        url = f"{self._dataverse_url}/api/data/v9.2/WhoAmI()"
        try:
            with _httpx.Client(timeout=5.0) as client:
                response = client.get(url, headers=self._auth_headers())
            return response.status_code == 200
        except Exception as exc:  # noqa: BLE001
            print(f"Dataverse health check failed: {exc}")
            return False
