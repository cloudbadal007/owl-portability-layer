"""AWS Amazon Bedrock AgentCore Semantic Adapter.

Cedar answers: Is this principal permitted to invoke this tool?
OWL/SHACL answers: Does this action violate our domain constraints?
Both run. Cedar via AgentCore Gateway. OWL/SHACL via this adapter.
Neither replaces the other.

Cedar only sees traffic through the AgentCore Gateway.
Cross-platform A2A delegations to Salesforce, ServiceNow,
or other non-AgentCore systems bypass the Gateway.
OWL/SHACL validation runs before routing — closing the
cross-platform gap Cedar cannot see.

When you leave AWS, delete this file.
Your OWL ontology and SHACL constraints remain unchanged.

Part of the OntoArc enterprise ontology toolkit.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyshacl
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

from owl_portability.adapters.base import BaseAdapter
from owl_portability.utils.shacl_reporter import violations_from_report

logger = logging.getLogger(__name__)

PROC = Namespace("http://enterprise.org/procurement#")

_BOTO3_AVAILABLE = False
_boto3: Any = None
try:
    import boto3 as _boto3_module

    _boto3 = _boto3_module
    _BOTO3_AVAILABLE = True
except ImportError:
    _BOTO3_AVAILABLE = False


@dataclass
class AgentCoreToolCall:
    """Inbound AgentCore Gateway tool invocation with Cedar decision metadata."""

    tool_call_id: str
    agent_identity_arn: str
    tool_name: str
    input_payload: dict[str, Any]
    gateway_arn: str
    cedar_decision: str
    semantic_class: str


class AgentCoreSemanticAdapter(BaseAdapter):
    """Bridge AgentCore Cedar policy outcomes with OWL/SHACL domain validation.

    Architecture:
      AgentCore Gateway (Cedar) → validates principal + tool + params
      This Adapter (OWL/SHACL)  → validates domain semantic validity
      Both must pass → tool executes

    Cedar scope:    AWS AgentCore Gateway boundary only
    OWL/SHACL scope: Cross-platform, vendor-neutral, pre-routing
    """

    TOOL_TO_OWL_CLASS_MAP: dict[str, str] = {
        "PaymentAPI__release_hold": "PaymentEvent",
        "PaymentAPI__approve_payment": "PaymentEvent",
        "ProcurementAPI__create_po": "Contract",
        "VendorAPI__update_vendor": "Vendor",
        "ComplianceAPI__log_hold": "ComplianceHold",
        "AnalyticsAPI__read_report": "ReadOnlyQuery",
    }

    def __init__(
        self,
        ontology_path: str,
        shacl_path: str,
        agentcore_region: str = "us-east-1",
        simulation_mode: bool = True,
    ) -> None:
        """Load ontology and SHACL graphs; configure AWS region and simulation mode.

        Args:
            ontology_path: Path to OWL ontology Turtle file.
            shacl_path: Path to SHACL shapes Turtle file.
            agentcore_region: AWS region for Bedrock AgentCore clients.
            simulation_mode: When True, skip live AWS API calls (default).
        """
        self._agentcore_region = agentcore_region
        self._simulation_mode = simulation_mode
        self._ontology = Graph()
        self._shacl = Graph()
        self._ontology.parse(Path(ontology_path).as_posix(), format="turtle")
        self._shacl.parse(Path(shacl_path).as_posix(), format="turtle")

    @property
    def platform_name(self) -> str:
        """Return stable adapter platform identifier."""
        return "aws_agentcore"

    def validate_tool_call(self, tool_call: AgentCoreToolCall) -> tuple[bool, list[str]]:
        """Run OWL/SHACL validation after Cedar permit; short-circuit on Cedar deny.

        Args:
            tool_call: Gateway tool invocation with Cedar decision and payload.

        Returns:
            Tuple of (semantic_valid, violation_messages).
        """
        if tool_call.cedar_decision == "deny":
            return False, ["Cedar policy denied this tool call."]

        owl_class = self.TOOL_TO_OWL_CLASS_MAP.get(tool_call.tool_name)
        if owl_class is None:
            msg = (
                f"🚨 UNKNOWN TOOL: {tool_call.tool_name} has no OWL semantic class mapping.\n"
                "Cannot validate. Fail-closed."
            )
            return False, [msg]

        data_graph = self._build_payload_rdf(tool_call, owl_class)
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
            return False, [f"Validation engine error: {exc}"]

        if conforms:
            return True, []

        violations = violations_from_report(report_graph, report_text)
        if not violations and report_text:
            violations = [report_text.strip()]
        violations = self._enrich_compliance_hold_violations(tool_call, violations)
        return False, violations

    def _enrich_compliance_hold_violations(
        self,
        tool_call: AgentCoreToolCall,
        violations: list[str],
    ) -> list[str]:
        """Add domain-friendly Legal approval message when ComplianceHold lacks approver."""
        payload = tool_call.input_payload
        if payload.get("holdType") == "ComplianceHold" and not payload.get("approvedBy"):
            friendly = "ComplianceHold requires Legal approval before release."
            if not any("Legal approval" in v for v in violations):
                violations = list(violations) + [friendly]
        return violations

    def _build_payload_rdf(self, tool_call: AgentCoreToolCall, owl_class: str) -> Graph:
        """Map AgentCore tool input payload keys to procurement ontology triples.

        Args:
            tool_call: Tool call with ``input_payload`` dict.
            owl_class: OWL class local name from ``TOOL_TO_OWL_CLASS_MAP``.

        Returns:
            RDF graph for the entity and nested hold nodes.
        """
        g = Graph()
        payload = tool_call.input_payload
        root = URIRef(
            f"http://enterprise.org/procurement/instance/{owl_class}/{tool_call.tool_call_id}"
        )
        g.add((root, RDF.type, PROC[owl_class]))

        if "amount" in payload:
            g.add(
                (root, PROC.amountUSD, Literal(Decimal(str(payload["amount"])), datatype=XSD.decimal))
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
        if "vendorId" in payload:
            g.add(
                (root, PROC.vendorId, Literal(str(payload["vendorId"]), datatype=XSD.string))
            )

        hold_type = payload.get("holdType")
        if hold_type:
            hold_node: URIRef | BNode = URIRef(
                f"http://enterprise.org/procurement/instance/{hold_type}/"
                f"{tool_call.tool_call_id}"
            )
            g.add((hold_node, RDF.type, PROC[str(hold_type)]))
            g.add((root, PROC.hasHoldStatus, hold_node))
            approved_by = payload.get("approvedBy")
            if approved_by:
                approver = Literal(str(approved_by), datatype=XSD.string)
                g.add((hold_node, PROC.holdApprovedBy, approver))
                g.add((root, PROC.holdApprovedBy, approver))
        elif payload.get("approvedBy"):
            g.add(
                (
                    root,
                    PROC.holdApprovedBy,
                    Literal(str(payload["approvedBy"]), datatype=XSD.string),
                )
            )

        return g

    def log_semantic_decision(
        self,
        tool_call: AgentCoreToolCall,
        semantic_valid: bool,
        violations: list[str],
    ) -> None:
        """Emit structured decision log (stdout in simulation, CloudWatch in production).

        Args:
            tool_call: Original tool invocation.
            semantic_valid: Result of ``validate_tool_call`` (ignored when Cedar denied).
            violations: SHACL or policy violation messages.
        """
        entry: dict[str, Any] = {
            **asdict(tool_call),
            "semantic_valid": semantic_valid,
            "violations": violations,
            "final_decision": (
                "PERMIT"
                if tool_call.cedar_decision == "permit" and semantic_valid
                else "DENY"
            ),
        }
        if self._simulation_mode:
            print(json.dumps(entry, indent=2, default=str))
            return

        if not _BOTO3_AVAILABLE:
            print(
                "boto3 is not installed. Install boto3>=1.34.0 for production "
                "CloudWatch logging."
            )
            return

        try:
            client = _boto3.client("logs", region_name=self._agentcore_region)
            client.put_log_events(
                logGroupName="/agentcore/semantic-validation",
                logStreamName=tool_call.tool_call_id,
                logEvents=[
                    {
                        "timestamp": int(__import__("time").time() * 1000),
                        "message": json.dumps(entry, default=str),
                    }
                ],
            )
        except Exception as exc:  # noqa: BLE001
            print(f"AgentCore semantic log write failed: {exc}")

    def write(self, entity_data: dict[str, Any], entity_class: str) -> bool:
        """Register validated entity in AgentCore Memory (simulated or live).

        Args:
            entity_data: Validated business payload.
            entity_class: OWL class local name.

        Returns:
            True on success.
        """
        if self._simulation_mode:
            print(f"[AgentCore simulation] write entity_class={entity_class}")
            print(f"  entity_data={entity_data}")
            return True

        if not _BOTO3_AVAILABLE:
            print(
                "boto3 is not installed. Install boto3>=1.34.0 for production "
                "AgentCore Memory writes."
            )
            return False

        try:
            client = _boto3.client(
                "bedrock-agentcore",
                region_name=self._agentcore_region,
            )
            client.create_memory_item(
                memoryId="owl-portability-validated",
                item={
                    "entityClass": entity_class,
                    "entityData": entity_data,
                    "source": "owl_portability_layer",
                },
            )
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"AgentCore Memory write failed for {entity_class}: {exc}")
            return False

    def read(self, entity_class: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Query AgentCore Memory for entities of a given OWL class.

        Args:
            entity_class: OWL class to filter on.
            filters: Query filters (adapter-specific).

        Returns:
            Matching entity dicts, or simulation placeholder.
        """
        if self._simulation_mode:
            return [
                {
                    "entity_class": entity_class,
                    "source": "agentcore",
                    "simulation": True,
                    "filters": filters,
                }
            ]

        if not _BOTO3_AVAILABLE:
            print(
                "boto3 is not installed. Install boto3>=1.34.0 for production "
                "AgentCore Memory reads."
            )
            return []

        try:
            client = _boto3.client(
                "bedrock-agentcore",
                region_name=self._agentcore_region,
            )
            response = client.list_memory_items(
                memoryId="owl-portability-validated",
                entityClass=entity_class,
                **filters,
            )
            items = response.get("items", [])
            return [item.get("entityData", item) for item in items]
        except Exception as exc:  # noqa: BLE001
            print(f"AgentCore Memory read failed for {entity_class}: {exc}")
            return []

    def health_check(self) -> bool:
        """Return True if AgentCore / Bedrock endpoint is reachable."""
        if self._simulation_mode:
            return True

        if not _BOTO3_AVAILABLE:
            print(
                "boto3 is not installed. Install boto3>=1.34.0 for production "
                "health checks."
            )
            return False

        try:
            client = _boto3.client("bedrock", region_name=self._agentcore_region)
            client.list_foundation_models(maxResults=1)
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"AgentCore health check failed: {exc}")
            return False
