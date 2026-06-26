"""Tests for OpenAI Frontier adapter (Business Context vs constraint proof).

Part of the enterprise ontology governance stack.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from owl_portability.adapters.openai_frontier import (  # noqa: E402
    FrontierAgentAction,
    FrontierValidationResult,
    OpenAIFrontierAdapter,
)


@pytest.fixture
def adapter() -> OpenAIFrontierAdapter:
    """OpenAI Frontier adapter in simulation mode with the procurement ontology."""
    return OpenAIFrontierAdapter(
        ontology_path=str(ROOT / "ontologies" / "procurement.ttl"),
        shacl_path=str(ROOT / "ontologies" / "procurement_shacl.ttl"),
        simulation_mode=True,
    )


def _compliance_hold_action(
    *,
    frontier_permitted: bool = True,
    approved_by: str | None = None,
    entity_class: str = "ComplianceHold",
) -> FrontierAgentAction:
    payload: dict = {
        "paymentId": "PAY-TEST",
        "amountUSD": 340000,
        "holdType": "ComplianceHold",
    }
    if approved_by:
        payload["approvedBy"] = approved_by
    return FrontierAgentAction(
        action_id="fr-test",
        agent_identity="frontier-test-agent@org.frontier",
        action_type="release_compliance_hold",
        entity_class=entity_class,
        payload=payload,
        frontier_context={"entity_type": "compliance_hold"},
        frontier_permitted=frontier_permitted,
    )


def test_frontier_denied_skips_shacl(adapter: OpenAIFrontierAdapter) -> None:
    """Frontier denial is sufficient — SHACL not invoked.

    Consistent with Cedar, IBM, and Dataverse adapter patterns.
    Platform governance denial short-circuits semantic validation.
    """
    result = adapter.validate_action(_compliance_hold_action(frontier_permitted=False))
    assert result.frontier_permitted is False
    assert result.shacl_valid is False
    assert result.safe_to_execute is False
    assert result.violations == ["Frontier governance denied this action."]


def test_frontier_permitted_shacl_blocks(adapter: OpenAIFrontierAdapter) -> None:
    """Frontier's Business Context understood the entity.

    OWL/SHACL caught what Business Context cannot enforce.
    This is the core gap in all three platforms: understanding
    does not equal formal constraint enforcement.
    """
    result = adapter.validate_action(_compliance_hold_action(frontier_permitted=True))
    assert result.frontier_permitted is True
    assert result.shacl_valid is False
    assert result.safe_to_execute is False
    assert any("Legal approval" in v for v in result.violations)


def test_both_layers_pass(adapter: OpenAIFrontierAdapter) -> None:
    """All three governance layers pass.

    Frontier permitted. OWL/SHACL validated. Execute.
    """
    result = adapter.validate_action(
        _compliance_hold_action(
            frontier_permitted=True,
            approved_by="sarah.chen@legal.enterprise.com",
        )
    )
    assert result.frontier_permitted is True
    assert result.shacl_valid is True
    assert result.safe_to_execute is True


def test_frontier_to_owl_mapping() -> None:
    """Frontier Business Context uses natural-language entity names.

    FRONTIER_TO_OWL_MAP bridges Frontier vocabulary to formal OWL class names.
    """
    assert OpenAIFrontierAdapter.FRONTIER_TO_OWL_MAP["compliance_hold"] == "ComplianceHold"
    assert OpenAIFrontierAdapter.FRONTIER_TO_OWL_MAP["payment_event"] == "PaymentEvent"


def test_safe_to_execute_requires_both_layers() -> None:
    """AND logic: both Frontier governance AND OWL/SHACL must pass.

    Consistent across all nine platform adapters.
    """
    frontier_invalid = FrontierValidationResult(
        action_id="r1",
        agent_identity="a1",
        frontier_permitted=True,
        shacl_valid=False,
    )
    frontier_denied = FrontierValidationResult(
        action_id="r2",
        agent_identity="a2",
        frontier_permitted=False,
        shacl_valid=True,
    )
    both_pass = FrontierValidationResult(
        action_id="r3",
        agent_identity="a3",
        frontier_permitted=True,
        shacl_valid=True,
    )
    assert frontier_invalid.safe_to_execute is False
    assert frontier_denied.safe_to_execute is False
    assert both_pass.safe_to_execute is True


def test_write_simulation_mode(adapter: OpenAIFrontierAdapter) -> None:
    """Simulation mode returns True without credentials."""
    assert adapter.write({"paymentId": "P-1"}, "PaymentEvent") is True


def test_health_check_simulation(adapter: OpenAIFrontierAdapter) -> None:
    """Health check succeeds offline when simulation_mode is enabled."""
    assert adapter.health_check() is True


def test_platform_name(adapter: OpenAIFrontierAdapter) -> None:
    """Platform identifier is stable for routing and metrics."""
    assert adapter.platform_name == "openai_frontier"


def test_read_simulation_mode(adapter: OpenAIFrontierAdapter) -> None:
    """Simulation read returns a placeholder without credentials."""
    rows = adapter.read("PaymentEvent", {"paymentId": "P-1"})
    assert len(rows) == 1
    assert rows[0]["source"] == "openai_frontier"
    assert rows[0]["simulation"] is True


def test_adapters_package_exports() -> None:
    """FrontierAgentAction and FrontierValidationResult are importable from adapters."""
    from owl_portability.adapters import (
        FrontierAgentAction as ActionFromPackage,
        FrontierValidationResult as ResultFromPackage,
        OpenAIFrontierAdapter as AdapterFromPackage,
    )

    assert AdapterFromPackage is OpenAIFrontierAdapter
    assert ActionFromPackage is FrontierAgentAction
    assert ResultFromPackage is FrontierValidationResult


def test_build_entity_rdf_maps_hold_and_approver(adapter: OpenAIFrontierAdapter) -> None:
    """_build_entity_rdf maps holdType and approvedBy to procurement ontology triples."""
    from rdflib import Literal, Namespace
    from rdflib.namespace import RDF, XSD

    proc = Namespace("http://enterprise.org/procurement#")
    action = _compliance_hold_action(
        approved_by="legal@enterprise.com",
        entity_class="compliance_hold",
    )
    graph = adapter._build_entity_rdf(action, "ComplianceHold")  # noqa: SLF001
    assert (None, RDF.type, proc.ComplianceHold) in graph
    assert (
        None,
        proc.holdApprovedBy,
        Literal("legal@enterprise.com", datatype=XSD.string),
    ) in graph


def test_payment_event_frontier_permitted_passes_shacl(
    adapter: OpenAIFrontierAdapter,
) -> None:
    """Valid PaymentEvent passes SHACL when Frontier permits the action."""
    action = FrontierAgentAction(
        action_id="fr-pay",
        agent_identity="finance-agent@org.frontier",
        action_type="approve_payment",
        entity_class="payment_event",
        payload={"paymentId": "PAY-OK", "amountUSD": 25000},
        frontier_context={"entity_type": "payment_event"},
        frontier_permitted=True,
    )
    result = adapter.validate_action(action)
    assert result.frontier_permitted is True
    assert result.shacl_valid is True
    assert result.safe_to_execute is True


def test_demo_case_frontier_permitted_shacl_blocked(
    adapter: OpenAIFrontierAdapter,
) -> None:
    """Mirrors demo_frontier_governance.py Test 1: Frontier permit, SHACL block."""
    result = adapter.validate_action(
        FrontierAgentAction(
            action_id="fr-001",
            agent_identity="finance-analytics-agent@org.frontier",
            action_type="release_compliance_hold",
            entity_class="ComplianceHold",
            payload={
                "paymentId": "PAY-001",
                "amountUSD": 340000,
                "holdType": "ComplianceHold",
            },
            frontier_context={
                "entity_type": "compliance_hold",
                "workflow": "legal_approval_workflow",
            },
            frontier_permitted=True,
        )
    )
    assert result.frontier_permitted is True
    assert result.shacl_valid is False
    assert result.safe_to_execute is False


def test_demo_case_both_layers_pass(adapter: OpenAIFrontierAdapter) -> None:
    """Mirrors demo_frontier_governance.py Test 2: all three layers pass."""
    result = adapter.validate_action(
        FrontierAgentAction(
            action_id="fr-002",
            agent_identity="legal-compliance-agent@org.frontier",
            action_type="release_compliance_hold",
            entity_class="ComplianceHold",
            payload={
                "paymentId": "PAY-001",
                "amountUSD": 340000,
                "holdType": "ComplianceHold",
                "approvedBy": "sarah.chen@legal.enterprise.com",
            },
            frontier_context={"approval_status": "Legal sign-off recorded"},
            frontier_permitted=True,
        )
    )
    assert result.safe_to_execute is True


def test_demo_case_frontier_denied_skips_shacl(adapter: OpenAIFrontierAdapter) -> None:
    """Mirrors demo_frontier_governance.py Test 3: Frontier deny, SHACL skipped."""
    result = adapter.validate_action(
        FrontierAgentAction(
            action_id="fr-003",
            agent_identity="analytics-readonly@org.frontier",
            action_type="release_compliance_hold",
            entity_class="ComplianceHold",
            payload={"paymentId": "PAY-002", "amountUSD": 50000},
            frontier_context={"permissions": "read_only"},
            frontier_permitted=False,
        )
    )
    assert result.frontier_permitted is False
    assert result.safe_to_execute is False
    assert result.violations == ["Frontier governance denied this action."]


def test_nine_platform_demo_imports() -> None:
    """Integration test: all nine platform adapters instantiate without conflicts.

    Nine platforms, one constraint layer, zero import errors.
    """
    from owl_portability.adapters.agentcore import AgentCoreSemanticAdapter
    from owl_portability.adapters.dataverse import DataverseSemanticAdapter
    from owl_portability.adapters.fabric_iq import FabricIQAdapter
    from owl_portability.adapters.google_knowledge_catalog import (
        GoogleKnowledgeCatalogAdapter,
    )
    from owl_portability.adapters.grok_databricks import GrokDatabricksAdapter
    from owl_portability.adapters.ibm_watsonx import IBMWatsonxContextAdapter
    from owl_portability.adapters.palantir import PalantirFoundryAdapter
    from owl_portability.adapters.servicenow import ServiceNowContextEngineAdapter

    onto = str(ROOT / "ontologies" / "procurement.ttl")
    shacl = str(ROOT / "ontologies" / "procurement_shacl.ttl")

    simulation_adapters = [
        GrokDatabricksAdapter(
            ontology_path=onto,
            shacl_path=shacl,
            simulation_mode=True,
        ),
        OpenAIFrontierAdapter(
            ontology_path=onto,
            shacl_path=shacl,
            simulation_mode=True,
        ),
        IBMWatsonxContextAdapter(ontology_path=onto, shacl_path=shacl, simulation_mode=True),
        DataverseSemanticAdapter(ontology_path=onto, shacl_path=shacl, simulation_mode=True),
        AgentCoreSemanticAdapter(ontology_path=onto, shacl_path=shacl, simulation_mode=True),
        ServiceNowContextEngineAdapter(
            instance_url="https://example.service-now.com",
            username="demo",
            password="demo",
            simulation_mode=True,
        ),
        GoogleKnowledgeCatalogAdapter(project_id="demo-project"),
    ]

    http_only_adapters = [
        FabricIQAdapter(
            workspace_id="00000000-0000-0000-0000-000000000001",
            ontology_item_id="iq-ontology-1",
            token="",
        ),
        PalantirFoundryAdapter(
            foundry_url="https://example.palantirfoundry.com",
            token="",
            object_type_map={"PaymentEvent": "ri.fake.palantir.object-type.payment"},
        ),
    ]

    all_adapters = simulation_adapters + http_only_adapters
    assert len(all_adapters) == 9
    assert all(a.platform_name for a in all_adapters)
    assert all(a.health_check() is True for a in simulation_adapters)

    from owl_portability.adapters import (  # noqa: F401
        FrontierAgentAction,
        FrontierValidationResult,
        OpenAIFrontierAdapter as FrontierFromPackage,
    )

    assert FrontierFromPackage is OpenAIFrontierAdapter
