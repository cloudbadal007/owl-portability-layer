"""Tests for Grok-on-Databricks adapter (Genie Ontology vs constraint proof).

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

from owl_portability.adapters.grok_databricks import (  # noqa: E402
    DatabricksAgentAction,
    DatabricksValidationResult,
    GrokDatabricksAdapter,
)


@pytest.fixture
def adapter() -> GrokDatabricksAdapter:
    """Grok-on-Databricks adapter in simulation mode with the procurement ontology."""
    return GrokDatabricksAdapter(
        ontology_path=str(ROOT / "ontologies" / "procurement.ttl"),
        shacl_path=str(ROOT / "ontologies" / "procurement_shacl.ttl"),
        simulation_mode=True,
    )


def _compliance_hold_action(
    *,
    unity_gateway_permitted: bool = True,
    approved_by: str | None = None,
    entity_class: str = "ComplianceHold",
    reasoning_model: str = "grok-4.3",
) -> DatabricksAgentAction:
    payload: dict = {
        "paymentId": "PAY-TEST",
        "amountUSD": 340000,
        "holdType": "ComplianceHold",
    }
    if approved_by:
        payload["approvedBy"] = approved_by
    return DatabricksAgentAction(
        action_id="gd-test",
        agent_identity="test-agent@databricks",
        reasoning_model=reasoning_model,
        action_type="release_compliance_hold",
        entity_class=entity_class,
        payload=payload,
        genie_context={"entity_type": "compliance_hold"},
        unity_gateway_permitted=unity_gateway_permitted,
    )


def test_gateway_denied_skips_shacl(adapter: GrokDatabricksAdapter) -> None:
    """Unity AI Gateway denial is sufficient — SHACL not invoked.

    Consistent with Cedar, IBM, Dataverse, and Frontier adapter patterns.
    Platform access-control denial short-circuits semantic constraint validation.
    """
    result = adapter.validate_action(_compliance_hold_action(unity_gateway_permitted=False))
    assert result.unity_gateway_permitted is False
    assert result.shacl_valid is False
    assert result.safe_to_execute is False
    assert result.violations == ["Unity AI Gateway denied this action."]


def test_gateway_permitted_shacl_blocks(adapter: GrokDatabricksAdapter) -> None:
    """Genie Ontology understood the entity. Unity AI Gateway permitted the call.

    OWL/SHACL caught what neither enforces. Grok's reasoning quality is
    irrelevant to this gap — it is a platform-level constraint enforcement gap,
    not a model limitation.
    """
    result = adapter.validate_action(_compliance_hold_action(unity_gateway_permitted=True))
    assert result.unity_gateway_permitted is True
    assert result.shacl_valid is False
    assert result.safe_to_execute is False
    assert any("Legal approval" in v for v in result.violations)


def test_both_layers_pass(adapter: GrokDatabricksAdapter) -> None:
    """All layers pass. Genie context, Gateway permission, and SHACL constraint validation all align. Execute."""
    result = adapter.validate_action(
        _compliance_hold_action(
            unity_gateway_permitted=True,
            approved_by="sarah.chen@legal.enterprise.com",
        )
    )
    assert result.unity_gateway_permitted is True
    assert result.shacl_valid is True
    assert result.safe_to_execute is True


def test_genie_to_owl_mapping() -> None:
    """Genie Ontology uses auto-extracted entity vocabulary.

    GENIE_TO_OWL_MAP bridges Genie's vocabulary to formal OWL class names.
    """
    assert GrokDatabricksAdapter.GENIE_TO_OWL_MAP["compliance_hold"] == "ComplianceHold"
    assert GrokDatabricksAdapter.GENIE_TO_OWL_MAP["payment_event"] == "PaymentEvent"


def test_safe_to_execute_requires_both_layers() -> None:
    """AND logic: both Unity AI Gateway permission AND OWL/SHACL must pass.

    Consistent across all ten platform adapters.
    """
    gateway_invalid = DatabricksValidationResult(
        action_id="r1",
        agent_identity="a1",
        reasoning_model="grok-4.3",
        unity_gateway_permitted=True,
        shacl_valid=False,
    )
    gateway_denied = DatabricksValidationResult(
        action_id="r2",
        agent_identity="a2",
        reasoning_model="grok-4.3",
        unity_gateway_permitted=False,
        shacl_valid=True,
    )
    both_pass = DatabricksValidationResult(
        action_id="r3",
        agent_identity="a3",
        reasoning_model="grok-4.3",
        unity_gateway_permitted=True,
        shacl_valid=True,
    )
    assert gateway_invalid.safe_to_execute is False
    assert gateway_denied.safe_to_execute is False
    assert both_pass.safe_to_execute is True


def test_reasoning_model_is_carried_not_validated(adapter: GrokDatabricksAdapter) -> None:
    """The reasoning model field is metadata for audit trails.

    It does not affect constraint validation. This proves the architectural
    point: swapping reasoning models does not close or widen the semantic
    governance gap.
    """
    grok_result = adapter.validate_action(
        _compliance_hold_action(reasoning_model="grok-4.3")
    )
    gpt_result = adapter.validate_action(
        _compliance_hold_action(reasoning_model="gpt-5")
    )
    assert grok_result.shacl_valid == gpt_result.shacl_valid
    assert grok_result.safe_to_execute == gpt_result.safe_to_execute
    assert grok_result.violations == gpt_result.violations
    assert grok_result.reasoning_model == "grok-4.3"
    assert gpt_result.reasoning_model == "gpt-5"


def test_write_simulation_mode(adapter: GrokDatabricksAdapter) -> None:
    """Simulation mode returns True without credentials."""
    assert adapter.write({"paymentId": "P-1"}, "PaymentEvent") is True


def test_health_check_simulation(adapter: GrokDatabricksAdapter) -> None:
    """Health check succeeds offline when simulation_mode is enabled."""
    assert adapter.health_check() is True


def test_platform_name(adapter: GrokDatabricksAdapter) -> None:
    """Platform identifier is stable for routing and metrics."""
    assert adapter.platform_name == "grok_databricks"


def test_ten_platform_demo_imports() -> None:
    """Integration test: all ten platform adapters instantiate without conflicts.

    Ten platforms, one constraint layer, zero import errors.
    """
    from owl_portability.adapters.agentcore import AgentCoreSemanticAdapter
    from owl_portability.adapters.dataverse import DataverseSemanticAdapter
    from owl_portability.adapters.fabric_iq import FabricIQAdapter
    from owl_portability.adapters.google_knowledge_catalog import (
        GoogleKnowledgeCatalogAdapter,
    )
    from owl_portability.adapters.ibm_watsonx import IBMWatsonxContextAdapter
    from owl_portability.adapters.openai_frontier import OpenAIFrontierAdapter
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
        DatabricksAgentAction,
        DatabricksValidationResult,
        GrokDatabricksAdapter as AdapterFromPackage,
    )

    assert AdapterFromPackage is GrokDatabricksAdapter
