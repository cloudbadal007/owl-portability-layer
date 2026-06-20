"""OpenAI Frontier Semantic Adapter for the OWL Portability Layer.

OpenAI Frontier ships two of the three governance layers:
Layer 1 — Business Context: what does this entity mean?
Layer 2 — Identity + Permissions: who can call which action?
Layer 3 — OWL/SHACL (this adapter): are formal constraints met?
OpenAI ships layers 1 and 2. Build layer 3.

OpenAI Frontier workspace agents move to credit-based pricing
on July 6, 2026. Enterprise architects evaluating Frontier
should design the OWL/SHACL constraint layer before go-live,
not after.

When you leave OpenAI Frontier, delete this file.
Your OWL ontology and SHACL constraints remain unchanged.

Part of the enterprise ontology governance stack.
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
class FrontierAgentAction:
    """Inbound Frontier agent action with Business Context governance metadata.

    Attributes:
        action_id: Stable identifier for the agent action.
        agent_identity: Frontier agent identity.
        action_type: Action being attempted.
        entity_class: Business Context entity class.
        payload: Action parameters.
        frontier_context: Business Context resolution result.
        frontier_permitted: Frontier governance decision.
    """

    action_id: str
    agent_identity: str
    action_type: str
    entity_class: str
    payload: dict
    frontier_context: dict
    frontier_permitted: bool


@dataclass
class FrontierValidationResult:
    """Outcome of two-layer validation: Frontier governance plus OWL/SHACL.

    Attributes:
        action_id: Identifier of the validated action.
        agent_identity: Identity of the requesting agent.
        frontier_permitted: Frontier governance decision.
        shacl_valid: True when the data graph conforms to all SHACL shapes.
        violations: Human-readable constraint messages.
        safe_to_execute: True only when Frontier permits AND SHACL validates.
    """

    action_id: str
    agent_identity: str
    frontier_permitted: bool
    shacl_valid: bool
    violations: list[str] = field(default_factory=list)
    safe_to_execute: bool = False

    def __post_init__(self) -> None:
        """Both Frontier governance AND OWL/SHACL must pass."""
        self.safe_to_execute = self.frontier_permitted and self.shacl_valid


class OpenAIFrontierAdapter(BaseAdapter):
    """Bridge OpenAI Frontier Business Context with OWL/SHACL constraint proofs.

    Frontier vs Google Knowledge Catalog vs Microsoft Fabric IQ:

    Google Knowledge Catalog:  Best open standards (RDF/JSON-LD)
                               No formal constraint enforcement
    Microsoft Fabric IQ:       Closest to formal domain modelling
                               DirectLake boundary constraint
    OpenAI Frontier:           Most accessible business context setup
                               "AI co-worker" governance model
                               No OWL, no SHACL

    All three: OWL ❌ SHACL ❌
    """

    FRONTIER_TO_OWL_MAP: dict[str, str] = {
        "payment_event": "PaymentEvent",
        "compliance_hold": "ComplianceHold",
        "budget_hold": "BudgetHold",
        "vendor_dispute": "VendorDisputeHold",
        "vendor_record": "Vendor",
        "contract_record": "Contract",
        "ComplianceHold": "ComplianceHold",
        "PaymentEvent": "PaymentEvent",
        "BudgetHold": "BudgetHold",
        "Contract": "Contract",
        "Vendor": "Vendor",
    }

    def __init__(
        self,
        ontology_path: str,
        shacl_path: str,
        frontier_api_key: str = "",
        frontier_org_id: str = "",
        simulation_mode: bool = True,
    ) -> None:
        """Load ontology and SHACL graphs; configure Frontier API access.

        Args:
            ontology_path: Path to OWL ontology Turtle file.
            shacl_path: Path to SHACL shapes Turtle file.
            frontier_api_key: OpenAI Frontier API key for production mode.
            frontier_org_id: OpenAI organization ID for production mode.
            simulation_mode: When True, skip live Frontier API calls (default).
        """
        self._frontier_api_key = frontier_api_key
        self._frontier_org_id = frontier_org_id
        self._simulation_mode = simulation_mode
        self._ontology = Graph()
        self._shacl = Graph()
        self._ontology.parse(Path(ontology_path).as_posix(), format="turtle")
        self._shacl.parse(Path(shacl_path).as_posix(), format="turtle")

    @property
    def platform_name(self) -> str:
        """Return stable adapter platform identifier."""
        return "openai_frontier"

    def validate_action(self, action: FrontierAgentAction) -> FrontierValidationResult:
        """Run OWL/SHACL validation after Frontier permit; short-circuit on deny.

        Frontier's Business Context and OWL/SHACL are complementary layers.
        When Frontier denies, the action is already blocked — SHACL is not invoked.
        When Frontier permits, SHACL checks the formal domain constraint Business
        Context cannot express.

        Args:
            action: Frontier agent action with governance decision and payload.

        Returns:
            FrontierValidationResult with Frontier governance, SHACL, and safe_to_execute.
        """
        if not action.frontier_permitted:
            return FrontierValidationResult(
                action_id=action.action_id,
                agent_identity=action.agent_identity,
                frontier_permitted=False,
                shacl_valid=False,
                violations=["Frontier governance denied this action."],
            )

        owl_class = self.FRONTIER_TO_OWL_MAP.get(
            action.entity_class,
            action.entity_class,
        )
        data_graph = self._build_entity_rdf(action, owl_class)
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
            return FrontierValidationResult(
                action_id=action.action_id,
                agent_identity=action.agent_identity,
                frontier_permitted=True,
                shacl_valid=False,
                violations=[f"Validation engine error: {exc}"],
            )

        if conforms:
            return FrontierValidationResult(
                action_id=action.action_id,
                agent_identity=action.agent_identity,
                frontier_permitted=True,
                shacl_valid=True,
                violations=[],
            )

        violations = violations_from_report(report_graph, report_text)
        if not violations and report_text:
            violations = [report_text.strip()]
        violations = self._enrich_compliance_hold_violations(action, violations)
        return FrontierValidationResult(
            action_id=action.action_id,
            agent_identity=action.agent_identity,
            frontier_permitted=True,
            shacl_valid=False,
            violations=violations,
        )

    def _enrich_compliance_hold_violations(
        self,
        action: FrontierAgentAction,
        violations: list[str],
    ) -> list[str]:
        """Add domain-friendly Legal approval message when ComplianceHold lacks approver."""
        payload = action.payload
        hold_type = payload.get("holdType")
        is_compliance = (
            hold_type == "ComplianceHold"
            or action.entity_class in ("ComplianceHold", "compliance_hold")
        )
        if is_compliance and not payload.get("approvedBy"):
            friendly = "ComplianceHold requires Legal approval before release."
            if not any("Legal approval" in v for v in violations):
                violations = list(violations) + [friendly]
        return violations

    def _build_entity_rdf(self, action: FrontierAgentAction, owl_class: str) -> Graph:
        """Map Frontier payload keys to procurement ontology triples.

        Args:
            action: Frontier agent action with payload dict.
            owl_class: OWL class local name resolved from FRONTIER_TO_OWL_MAP.

        Returns:
            RDF graph for the entity and any nested hold node.
        """
        g = Graph()
        payload = action.payload
        root = URIRef(
            f"http://enterprise.org/procurement/instance/{owl_class}/{action.action_id}"
        )
        g.add((root, RDF.type, PROC[owl_class]))

        if "amountUSD" in payload or "amount" in payload:
            amount = payload.get("amountUSD", payload.get("amount"))
            g.add(
                (
                    root,
                    PROC.amountUSD,
                    Literal(Decimal(str(amount)), datatype=XSD.decimal),
                )
            )
        if "paymentId" in payload:
            g.add(
                (root, PROC.paymentId, Literal(str(payload["paymentId"]), datatype=XSD.string))
            )
        if "contractValue" in payload:
            g.add(
                (
                    root,
                    PROC.contractValue,
                    Literal(Decimal(str(payload["contractValue"])), datatype=XSD.decimal),
                )
            )

        hold_type = payload.get("holdType")
        approved_by = payload.get("approvedBy")
        if hold_type:
            hold_node: URIRef | BNode = URIRef(
                f"http://enterprise.org/procurement/instance/{hold_type}/{action.action_id}"
            )
            g.add((hold_node, RDF.type, PROC[str(hold_type)]))
            g.add((root, PROC.hasHoldStatus, hold_node))
            if approved_by:
                approver = Literal(str(approved_by), datatype=XSD.string)
                g.add((hold_node, PROC.holdApprovedBy, approver))
                g.add((root, PROC.holdApprovedBy, approver))
        elif approved_by:
            g.add(
                (
                    root,
                    PROC.holdApprovedBy,
                    Literal(str(approved_by), datatype=XSD.string),
                )
            )

        return g

    def _auth_headers(self) -> dict[str, str]:
        """Build HTTP headers for OpenAI Frontier API calls."""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._frontier_api_key:
            headers["Authorization"] = f"Bearer {self._frontier_api_key}"
        if self._frontier_org_id:
            headers["OpenAI-Organization"] = self._frontier_org_id
        return headers

    def write(self, entity_data: dict[str, Any], entity_class: str) -> bool:
        """Persist a validated entity to Frontier (simulated or live).

        Args:
            entity_data: Validated business payload.
            entity_class: OWL class local name.

        Returns:
            True on success.
        """
        if self._simulation_mode:
            print(f"[OpenAI Frontier simulation] write entity_class={entity_class}")
            print(f"  entity_data={entity_data}")
            return True

        if not _HTTPX_AVAILABLE:
            print(
                "httpx is not installed. Install httpx>=0.27.0 for production "
                "OpenAI Frontier writes."
            )
            return False

        url = "https://api.openai.com/v1/frontier/entities"
        try:
            with _httpx.Client(timeout=10.0) as client:
                response = client.post(
                    url,
                    json={"entityClass": entity_class, "entityData": entity_data},
                    headers=self._auth_headers(),
                )
            return response.status_code in (200, 201, 204)
        except Exception as exc:  # noqa: BLE001
            print(f"OpenAI Frontier write failed for {entity_class}: {exc}")
            return False

    def read(self, entity_class: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Query Frontier entities (simulated or live).

        Args:
            entity_class: OWL class to filter on.
            filters: Field filters passed as query params in production mode.

        Returns:
            Matching entity dicts, or simulation placeholder.
        """
        if self._simulation_mode:
            return [
                {
                    "entity_class": entity_class,
                    "source": "openai_frontier",
                    "simulation": True,
                    "filters": filters,
                }
            ]

        if not _HTTPX_AVAILABLE:
            print(
                "httpx is not installed. Install httpx>=0.27.0 for production "
                "OpenAI Frontier reads."
            )
            return []

        url = (
            f"https://api.openai.com/v1/frontier/entities/"
            f"{quote(str(entity_class), safe='')}"
        )
        try:
            with _httpx.Client(timeout=10.0) as client:
                response = client.get(url, params=filters, headers=self._auth_headers())
            if response.status_code != 200:
                return []
            body = response.json()
            return body.get("value", body if isinstance(body, list) else [])
        except Exception as exc:  # noqa: BLE001
            print(f"OpenAI Frontier read failed for {entity_class}: {exc}")
            return []

    def health_check(self) -> bool:
        """Return True if the OpenAI Frontier endpoint is reachable."""
        if self._simulation_mode:
            return True

        if not _HTTPX_AVAILABLE:
            print(
                "httpx is not installed. Install httpx>=0.27.0 for production "
                "OpenAI Frontier health checks."
            )
            return False

        url = "https://api.openai.com/v1/frontier/health"
        try:
            with _httpx.Client(timeout=5.0) as client:
                response = client.get(url, headers=self._auth_headers())
            return response.status_code == 200
        except Exception as exc:  # noqa: BLE001
            print(f"OpenAI Frontier health check failed: {exc}")
            return False
