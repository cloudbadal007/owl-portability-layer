"""IBM watsonx.data Context Adapter for the OWL Portability Layer.

IBM watsonx.data Context claims to enforce governance at runtime —
the closest any platform has come to the OWL/SHACL argument.
The precise distinction: IBM enforces policies (rules about
permitted actions). OWL/SHACL enforces formal proofs (constraint
satisfaction that is machine-readable and auditable).
Both are necessary. IBM ships policies. Build the proofs.

IBM's federated, open-standards, and cross-cloud claims make it
the most architecturally interesting new entrant in the
seven-platform matrix. watsonx.data Context is in private preview
as of Think 2026. Production validation pending.

When IBM's Context layer evolves from private preview to GA,
update the production methods. Your OWL ontology and SHACL
constraints remain unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional
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
class WatsonxContextQuery:
    """Inbound watsonx.data Context action with IBM runtime governance metadata.

    Attributes:
        query_id: Stable identifier for the agent action.
        agent_id: Identity of the requesting agent.
        action_type: Business action the agent attempts (e.g. release_compliance_hold).
        entity_class: IBM or OWL entity class name for the focus resource.
        payload: Business payload for the action.
        watsonx_context: Federated context resolved by watsonx.data.
        ibm_governance_decision: IBM runtime decision, "permit" or "deny".
        watsonx_semantic_class: Optional IBM semantic class tag overriding entity_class.
    """

    query_id: str
    agent_id: str
    action_type: str
    entity_class: str
    payload: dict
    watsonx_context: dict
    ibm_governance_decision: str
    watsonx_semantic_class: Optional[str] = None

@dataclass
class WatsonxValidationResult:
    """Outcome of two-layer validation: IBM runtime governance plus OWL/SHACL.

    Attributes:
        query_id: Identifier of the validated query.
        agent_id: Identity of the requesting agent.
        ibm_governance: IBM's runtime decision ("permit" or "deny").
        shacl_valid: True when the data graph conforms to all SHACL shapes.
        violations: Human-readable constraint messages.
        safe_to_execute: True only when IBM permits AND SHACL validates.
    """

    query_id: str
    agent_id: str
    ibm_governance: str
    shacl_valid: bool
    violations: list[str] = field(default_factory=list)
    safe_to_execute: bool = False

    def __post_init__(self) -> None:
        """Both layers must pass — IBM policy AND OWL/SHACL proof."""
        self.safe_to_execute = (
            self.ibm_governance == "permit" and self.shacl_valid
        )

class IBMWatsonxContextAdapter(BaseAdapter):
    """Bridge IBM watsonx.data Context runtime governance with OWL/SHACL proofs.

    Seven-Platform Matrix Position:

    IBM watsonx.data Context vs Google Knowledge Catalog vs AWS AgentCore:

    Google:  Open standards (RDF/JSON-LD). Best retrieval.
             No formal constraint enforcement.

    AWS:     Best governance authoring (Cedar). Formally verifiable.
             Gateway-scope only — cross-platform gap open.

    IBM:     Federated + open standards + runtime governance claim.
             Policy-based, not formally provable. Private preview.
             Closest to OWL/SHACL argument of any platform.

    All three: OWL ❌ SHACL ❌
    """

    IBM_TO_OWL_MAP: dict[str, str] = {
        "payment_event": "PaymentEvent",
        "compliance_hold": "ComplianceHold",
        "budget_hold": "BudgetHold",
        "vendor_dispute": "VendorDisputeHold",
        "vendor_record": "Vendor",
        "contract_record": "Contract",
        "PaymentEvent": "PaymentEvent",
        "ComplianceHold": "ComplianceHold",
        "BudgetHold": "BudgetHold",
        "Contract": "Contract",
        "Vendor": "Vendor",
    }

    def __init__(
        self,
        ontology_path: str,
        shacl_path: str,
        watsonx_url: str = "",
        api_key: str = "",
        simulation_mode: bool = True,
    ) -> None:
        """Load ontology and SHACL graphs; configure watsonx.data Context access.

        Args:
            ontology_path: Path to OWL ontology Turtle file.
            shacl_path: Path to SHACL shapes Turtle file.
            watsonx_url: watsonx.data instance URL (e.g. https://instance.cloud.ibm.com).
            api_key: IBM Cloud API key for the watsonx.data Context API.
            simulation_mode: When True, skip live IBM API calls (default).
        """
        self._watsonx_url = watsonx_url.rstrip("/")
        self._api_key = api_key
        self._simulation_mode = simulation_mode
        self._ontology = Graph()
        self._shacl = Graph()
        self._ontology.parse(Path(ontology_path).as_posix(), format="turtle")
        self._shacl.parse(Path(shacl_path).as_posix(), format="turtle")

    @property
    def platform_name(self) -> str:
        """Return stable adapter platform identifier."""
        return "ibm_watsonx_context"

    def validate_with_shacl(
        self, query: WatsonxContextQuery
    ) -> WatsonxValidationResult:
        """Run OWL/SHACL validation after IBM permit; short-circuit on IBM deny.

        IBM's runtime governance and OWL/SHACL are complementary layers.
        When IBM denies, the action is already blocked — SHACL is not invoked.
        When IBM permits, SHACL checks the formal domain constraint IBM's
        policy cannot express.

        Args:
            query: watsonx.data Context query with IBM decision and payload.

        Returns:
            WatsonxValidationResult with IBM governance, SHACL, and safe_to_execute.
        """
        if query.ibm_governance_decision == "deny":
            return WatsonxValidationResult(
                query_id=query.query_id,
                agent_id=query.agent_id,
                ibm_governance="deny",
                shacl_valid=False,
                violations=["IBM watsonx.data Context denied this action."],
            )

        owl_class = self.IBM_TO_OWL_MAP.get(
            query.watsonx_semantic_class or query.entity_class,
            query.watsonx_semantic_class or query.entity_class,
        )
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
            return WatsonxValidationResult(
                query_id=query.query_id,
                agent_id=query.agent_id,
                ibm_governance="permit",
                shacl_valid=False,
                violations=[f"Validation engine error: {exc}"],
            )

        if conforms:
            return WatsonxValidationResult(
                query_id=query.query_id,
                agent_id=query.agent_id,
                ibm_governance="permit",
                shacl_valid=True,
                violations=[],
            )

        violations = violations_from_report(report_graph, report_text)
        if not violations and report_text:
            violations = [report_text.strip()]
        violations = self._enrich_compliance_hold_violations(query, violations)
        return WatsonxValidationResult(
            query_id=query.query_id,
            agent_id=query.agent_id,
            ibm_governance="permit",
            shacl_valid=False,
            violations=violations,
        )

    def _enrich_compliance_hold_violations(
        self,
        query: WatsonxContextQuery,
        violations: list[str],
    ) -> list[str]:
        """Add domain-friendly Legal approval message when ComplianceHold lacks approver."""
        payload = query.payload
        hold_type = payload.get("holdType")
        is_compliance = (
            hold_type == "ComplianceHold"
            or (query.watsonx_semantic_class or query.entity_class) == "ComplianceHold"
        )
        if is_compliance and not payload.get("approvedBy"):
            friendly = "ComplianceHold requires Legal approval before release."
            if not any("Legal approval" in v for v in violations):
                violations = list(violations) + [friendly]
        return violations

    def _build_entity_rdf(
        self, query: WatsonxContextQuery, owl_class: str
    ) -> Graph:
        """Map watsonx.data Context payload keys to procurement ontology triples.

        Args:
            query: Context query with IBM payload keys.
            owl_class: OWL class local name resolved from IBM_TO_OWL_MAP.

        Returns:
            RDF graph for the entity and any nested hold node.
        """
        g = Graph()
        payload = query.payload
        root = URIRef(
            f"http://enterprise.org/procurement/instance/{owl_class}/{query.query_id}"
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
                f"http://enterprise.org/procurement/instance/{hold_type}/{query.query_id}"
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
        """Build HTTP headers for watsonx.data Context API calls."""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def write(self, entity_data: dict[str, Any], entity_class: str) -> bool:
        """Persist a validated entity to watsonx.data Context (simulated or live).

        Args:
            entity_data: Validated business payload.
            entity_class: OWL class local name.

        Returns:
            True on success.
        """
        if self._simulation_mode:
            print(f"[IBM watsonx simulation] write entity_class={entity_class}")
            print(f"  entity_data={entity_data}")
            return True

        if not _HTTPX_AVAILABLE:
            print(
                "httpx is not installed. Install httpx>=0.27.0 for production "
                "watsonx.data Context writes."
            )
            return False

        url = f"{self._watsonx_url}/v1/entities"
        try:
            with _httpx.Client(timeout=10.0) as client:
                response = client.post(
                    url,
                    json={"entityClass": entity_class, "entityData": entity_data},
                    headers=self._auth_headers(),
                )
            return response.status_code in (200, 201, 204)
        except Exception as exc:  # noqa: BLE001
            print(f"IBM watsonx write failed for {entity_class}: {exc}")
            return False

    def read(self, entity_class: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Query watsonx.data Context entities (simulated or live).

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
                    "source": "ibm_watsonx",
                    "simulation": True,
                    "filters": filters,
                }
            ]

        if not _HTTPX_AVAILABLE:
            print(
                "httpx is not installed. Install httpx>=0.27.0 for production "
                "watsonx.data Context reads."
            )
            return []

        url = f"{self._watsonx_url}/v1/entities/{quote(str(entity_class), safe='')}"
        try:
            with _httpx.Client(timeout=10.0) as client:
                response = client.get(
                    url, params=filters, headers=self._auth_headers()
                )
            if response.status_code != 200:
                return []
            body = response.json()
            return body.get("value", body if isinstance(body, list) else [])
        except Exception as exc:  # noqa: BLE001
            print(f"IBM watsonx read failed for {entity_class}: {exc}")
            return []

    def health_check(self) -> bool:
        """Return True if the watsonx.data Context endpoint is reachable."""
        if self._simulation_mode:
            return True

        if not _HTTPX_AVAILABLE:
            print(
                "httpx is not installed. Install httpx>=0.27.0 for production "
                "watsonx.data Context health checks."
            )
            return False

        url = f"{self._watsonx_url}/v1/health"
        try:
            with _httpx.Client(timeout=5.0) as client:
                response = client.get(url, headers=self._auth_headers())
            return response.status_code == 200
        except Exception as exc:  # noqa: BLE001
            print(f"IBM watsonx health check failed: {exc}")
            return False
