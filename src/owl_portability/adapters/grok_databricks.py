"""Grok-on-Databricks Semantic Adapter for the OWL Portability Layer.

xAI's Grok now reasons over Databricks' Genie Ontology and operates
under Unity AI Gateway's runtime governance. Neither layer ships
formal OWL class hierarchies or SHACL constraint enforcement.

Genie Ontology answers:    What does this entity mean?
Unity AI Gateway answers:  Is this agent permitted to call this tool?
OWL/SHACL (this adapter):  Does this action satisfy formal constraints?

Grok brings reasoning capability. Databricks brings context and
access control. Neither brings formal constraint proof.

When you change reasoning models (Grok, GPT, Claude, Gemini) on
Databricks, this adapter is unaffected — it validates the entity,
not the model that reasoned about it.

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
class DatabricksAgentAction:
    """Inbound Databricks agent action with Genie Ontology and Gateway metadata.

    Attributes:
        action_id: Stable identifier for the agent action.
        agent_identity: Databricks agent identity.
        reasoning_model: Model that reasoned about the action (audit metadata only).
        action_type: Action being attempted.
        entity_class: Genie Ontology entity class.
        payload: Action parameters.
        genie_context: Genie Ontology resolution result.
        unity_gateway_permitted: Unity AI Gateway governance decision.
    """

    action_id: str
    agent_identity: str
    reasoning_model: str
    action_type: str
    entity_class: str
    payload: dict
    genie_context: dict
    unity_gateway_permitted: bool


@dataclass
class DatabricksValidationResult:
    """Outcome of two-layer validation: Unity AI Gateway plus OWL/SHACL.

    Attributes:
        action_id: Identifier of the validated action.
        agent_identity: Identity of the requesting agent.
        reasoning_model: Model that reasoned about the action (carried, not validated).
        unity_gateway_permitted: Unity AI Gateway governance decision.
        shacl_valid: True when the data graph conforms to all SHACL shapes.
        violations: Human-readable constraint messages.
        safe_to_execute: True only when Gateway permits AND SHACL validates.
    """

    action_id: str
    agent_identity: str
    reasoning_model: str
    unity_gateway_permitted: bool
    shacl_valid: bool
    violations: list[str] = field(default_factory=list)
    safe_to_execute: bool = False

    def __post_init__(self) -> None:
        """Unity AI Gateway permission AND OWL/SHACL must both pass."""
        self.safe_to_execute = self.unity_gateway_permitted and self.shacl_valid


class GrokDatabricksAdapter(BaseAdapter):
    """Bridge Databricks Genie Ontology with OWL/SHACL constraint proofs.

    Nine-Platform Matrix Position:

    Grok-on-Databricks vs the other eight platforms:

      Genie Ontology:     auto-extracted business context (not formal OWL)
      Unity AI Gateway:   runtime access control (not formal constraint proof)
      Grok 4.3:            1M token context, lowest hallucination rate
                           among frontier models — reasoning quality is real
                           and does not change the architectural gap

      The reasoning model is swappable (Grok, GPT, Claude on Agent Bricks).
      The gap is not swappable. It belongs to the platform, not the model.
    """

    GENIE_TO_OWL_MAP: dict[str, str] = {
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
        databricks_workspace_url: str = "",
        databricks_token: str = "",
        simulation_mode: bool = True,
    ) -> None:
        """Load ontology and SHACL graphs; configure Databricks API access.

        Args:
            ontology_path: Path to OWL ontology Turtle file.
            shacl_path: Path to SHACL shapes Turtle file.
            databricks_workspace_url: Databricks workspace URL for production mode.
            databricks_token: Databricks personal access token for production mode.
            simulation_mode: When True, skip live Databricks API calls (default).
        """
        self._databricks_workspace_url = databricks_workspace_url.rstrip("/")
        self._databricks_token = databricks_token
        self._simulation_mode = simulation_mode
        self._ontology = Graph()
        self._shacl = Graph()
        self._ontology.parse(Path(ontology_path).as_posix(), format="turtle")
        self._shacl.parse(Path(shacl_path).as_posix(), format="turtle")

    @property
    def platform_name(self) -> str:
        """Return stable adapter platform identifier."""
        return "grok_databricks"

    def validate_action(
        self, action: DatabricksAgentAction
    ) -> DatabricksValidationResult:
        """Run OWL/SHACL validation after Gateway permit; short-circuit on deny.

        Unity AI Gateway denial is sufficient — SHACL is not invoked when the
        Gateway already denied the action. When permitted, SHACL checks formal
        domain constraints that Genie Ontology cannot express.

        The reasoning_model field is carried through for audit trails but never
        affects validation logic.

        Args:
            action: Databricks agent action with governance decision and payload.

        Returns:
            DatabricksValidationResult with Gateway, SHACL, and safe_to_execute.
        """
        if not action.unity_gateway_permitted:
            return DatabricksValidationResult(
                action_id=action.action_id,
                agent_identity=action.agent_identity,
                reasoning_model=action.reasoning_model,
                unity_gateway_permitted=False,
                shacl_valid=False,
                violations=["Unity AI Gateway denied this action."],
            )

        owl_class = self.GENIE_TO_OWL_MAP.get(
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
            return DatabricksValidationResult(
                action_id=action.action_id,
                agent_identity=action.agent_identity,
                reasoning_model=action.reasoning_model,
                unity_gateway_permitted=True,
                shacl_valid=False,
                violations=[f"Validation engine error: {exc}"],
            )

        if conforms:
            return DatabricksValidationResult(
                action_id=action.action_id,
                agent_identity=action.agent_identity,
                reasoning_model=action.reasoning_model,
                unity_gateway_permitted=True,
                shacl_valid=True,
                violations=[],
            )

        violations = violations_from_report(report_graph, report_text)
        if not violations and report_text:
            violations = [report_text.strip()]
        violations = self._enrich_compliance_hold_violations(action, violations)
        return DatabricksValidationResult(
            action_id=action.action_id,
            agent_identity=action.agent_identity,
            reasoning_model=action.reasoning_model,
            unity_gateway_permitted=True,
            shacl_valid=False,
            violations=violations,
        )

    def _enrich_compliance_hold_violations(
        self,
        action: DatabricksAgentAction,
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

    def _build_entity_rdf(self, action: DatabricksAgentAction, owl_class: str) -> Graph:
        """Map Databricks payload keys to procurement ontology triples.

        Args:
            action: Databricks agent action with payload dict.
            owl_class: OWL class local name resolved from GENIE_TO_OWL_MAP.

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
        """Build HTTP headers for Databricks REST API calls."""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._databricks_token:
            headers["Authorization"] = f"Bearer {self._databricks_token}"
        return headers

    def write(self, entity_data: dict[str, Any], entity_class: str) -> bool:
        """Persist a validated entity to Unity Catalog (simulated or live).

        Args:
            entity_data: Validated business payload.
            entity_class: OWL class local name.

        Returns:
            True on success.
        """
        if self._simulation_mode:
            print(f"[Grok-on-Databricks simulation] write entity_class={entity_class}")
            print(f"  entity_data={entity_data}")
            return True

        if not _HTTPX_AVAILABLE:
            print(
                "httpx is not installed. Install httpx>=0.27.0 for production "
                "Databricks Unity Catalog writes."
            )
            return False

        url = f"{self._databricks_workspace_url}/api/2.1/unity-catalog/entities"
        try:
            with _httpx.Client(timeout=10.0) as client:
                response = client.post(
                    url,
                    json={"entityClass": entity_class, "entityData": entity_data},
                    headers=self._auth_headers(),
                )
            return response.status_code in (200, 201, 204)
        except Exception as exc:  # noqa: BLE001
            print(f"Grok-on-Databricks write failed for {entity_class}: {exc}")
            return False

    def read(self, entity_class: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Query Unity Catalog entities (simulated or live).

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
                    "source": "grok_databricks",
                    "simulation": True,
                    "filters": filters,
                }
            ]

        if not _HTTPX_AVAILABLE:
            print(
                "httpx is not installed. Install httpx>=0.27.0 for production "
                "Databricks Unity Catalog reads."
            )
            return []

        url = (
            f"{self._databricks_workspace_url}/api/2.1/unity-catalog/entities/"
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
            print(f"Grok-on-Databricks read failed for {entity_class}: {exc}")
            return []

    def health_check(self) -> bool:
        """Return True if the Databricks workspace endpoint is reachable."""
        if self._simulation_mode:
            return True

        if not _HTTPX_AVAILABLE:
            print(
                "httpx is not installed. Install httpx>=0.27.0 for production "
                "Databricks health checks."
            )
            return False

        url = f"{self._databricks_workspace_url}/api/2.0/clusters/list"
        try:
            with _httpx.Client(timeout=5.0) as client:
                response = client.get(url, headers=self._auth_headers())
            return response.status_code == 200
        except Exception as exc:  # noqa: BLE001
            print(f"Grok-on-Databricks health check failed: {exc}")
            return False
