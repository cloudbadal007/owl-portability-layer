"""Tests for IBM watsonx.data Context adapter (policy vs proof).

Part of the OntoArc enterprise ontology toolkit.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from owl_portability.adapters.ibm_watsonx import (  # noqa: E402
    IBMWatsonxContextAdapter,
    WatsonxContextQuery,
    WatsonxValidationResult,
)


@pytest.fixture
def adapter() -> IBMWatsonxContextAdapter:
    """IBM watsonx adapter in simulation mode with the procurement ontology."""
    return IBMWatsonxContextAdapter(
        ontology_path=str(ROOT / "ontologies" / "procurement.ttl"),
        shacl_path=str(ROOT / "ontologies" / "procurement_shacl.ttl"),
        simulation_mode=True,
    )


def _compliance_hold_query(
    *,
    ibm_decision: str = "permit",
    approved_by: str | None = None,
    entity_class: str = "ComplianceHold",
    semantic_class: str | None = "ComplianceHold",
) -> WatsonxContextQuery:
    payload: dict = {
        "paymentId": "PAY-TEST",
        "amountUSD": 340000,
        "holdType": "ComplianceHold",
    }
    if approved_by:
        payload["approvedBy"] = approved_by
    return WatsonxContextQuery(
        query_id="wx-test",
        agent_id="watsonx-test-agent",
        action_type="release_compliance_hold",
        entity_class=entity_class,
        payload=payload,
        watsonx_context={"federated_source": "ibm-cloud-us-south"},
        ibm_governance_decision=ibm_decision,
        watsonx_semantic_class=semantic_class,
    )


def test_ibm_deny_skips_shacl(adapter: IBMWatsonxContextAdapter) -> None:
    """IBM denial is sufficient — SHACL not invoked.

    Mirrors the Cedar short-circuit pattern in AgentCore adapter.
    IBM's runtime governance and OWL/SHACL are complementary layers.
    """
    result = adapter.validate_with_shacl(_compliance_hold_query(ibm_decision="deny"))
    assert result.ibm_governance == "deny"
    assert result.shacl_valid is False
    assert result.safe_to_execute is False
    assert result.violations == ["IBM watsonx.data Context denied this action."]


def test_ibm_permit_shacl_blocks(adapter: IBMWatsonxContextAdapter) -> None:
    """IBM's runtime policy permitted the action.

    OWL/SHACL catches the formal constraint IBM's policy missed.
    This is the policy vs proof gap — IBM enforces rules,
    SHACL enforces formally provable constraints.
    """
    result = adapter.validate_with_shacl(_compliance_hold_query(ibm_decision="permit"))
    assert result.ibm_governance == "permit"
    assert result.shacl_valid is False
    assert result.safe_to_execute is False
    assert any("Legal approval" in v for v in result.violations)


def test_both_layers_pass(adapter: IBMWatsonxContextAdapter) -> None:
    """Both IBM governance and OWL/SHACL pass.

    IBM permitted the action. SHACL validated the formal constraint.
    Both layers are required. Neither alone is sufficient.
    """
    result = adapter.validate_with_shacl(
        _compliance_hold_query(
            ibm_decision="permit",
            approved_by="sarah.chen@legal.enterprise.com",
        )
    )
    assert result.ibm_governance == "permit"
    assert result.shacl_valid is True
    assert result.safe_to_execute is True


def test_ibm_to_owl_class_mapping() -> None:
    """IBM watsonx uses its own semantic tagging vocabulary.

    IBM_TO_OWL_MAP bridges IBM's entity names to OWL class names.
    This is the vocabulary bridge between IBM's semantic layer
    and the formal OWL type hierarchy.
    """
    assert IBMWatsonxContextAdapter.IBM_TO_OWL_MAP["compliance_hold"] == "ComplianceHold"


def test_safe_to_execute_requires_both_layers() -> None:
    """Verifies AND logic: IBM governance AND SHACL must both pass.

    Matches the pattern across all platform adapters —
    platform governance + OWL/SHACL, both required.
    """
    permit_invalid = WatsonxValidationResult(
        query_id="r1", agent_id="a1", ibm_governance="permit", shacl_valid=False
    )
    deny_valid = WatsonxValidationResult(
        query_id="r2", agent_id="a2", ibm_governance="deny", shacl_valid=True
    )
    permit_valid = WatsonxValidationResult(
        query_id="r3", agent_id="a3", ibm_governance="permit", shacl_valid=True
    )
    assert permit_invalid.safe_to_execute is False
    assert deny_valid.safe_to_execute is False
    assert permit_valid.safe_to_execute is True


def test_write_simulation_mode(adapter: IBMWatsonxContextAdapter) -> None:
    """Simulation mode returns True without credentials."""
    assert adapter.write({"paymentId": "P-1"}, "PaymentEvent") is True


def test_health_check_simulation(adapter: IBMWatsonxContextAdapter) -> None:
    """Health check succeeds offline when simulation_mode is enabled."""
    assert adapter.health_check() is True


def test_platform_name(adapter: IBMWatsonxContextAdapter) -> None:
    """Platform identifier is stable for routing and metrics."""
    assert adapter.platform_name == "ibm_watsonx_context"


def test_seven_platform_demo_imports() -> None:
    """Integration test: all seven platform adapters can be instantiated together.

    The seven-platform demo requires all adapters to coexist without
    namespace or import conflicts.
    """
    from owl_portability.adapters.agentcore import AgentCoreSemanticAdapter
    from owl_portability.adapters.dataverse import DataverseSemanticAdapter
    from owl_portability.adapters.fabric_iq import FabricIQAdapter
    from owl_portability.adapters.google_knowledge_catalog import (
        GoogleKnowledgeCatalogAdapter,
    )
    from owl_portability.adapters.palantir import PalantirFoundryAdapter
    from owl_portability.adapters.servicenow import ServiceNowContextEngineAdapter

    onto = str(ROOT / "ontologies" / "procurement.ttl")
    shacl = str(ROOT / "ontologies" / "procurement_shacl.ttl")

    # Simulation-mode adapters resolve health offline without credentials.
    simulation_adapters = [
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

    # Palantir and Fabric IQ resolve health against live endpoints only.
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
    assert len(all_adapters) == 7
    assert all(a.platform_name for a in all_adapters)
    assert all(a.health_check() is True for a in simulation_adapters)
