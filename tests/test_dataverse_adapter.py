"""Tests for Microsoft Dataverse semantic adapter.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from rdflib import Namespace
from rdflib.namespace import RDF

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from owl_portability.adapters.agentcore import AgentCoreSemanticAdapter  # noqa: E402
from owl_portability.adapters.dataverse import (  # noqa: E402
    DataverseAgentQuery,
    DataverseSemanticAdapter,
    DataverseValidationResult,
)
from owl_portability.adapters.fabric_iq import FabricIQAdapter  # noqa: E402
from owl_portability.adapters.google_knowledge_catalog import (  # noqa: E402
    GoogleKnowledgeCatalogAdapter,
)
from owl_portability.adapters.palantir import PalantirFoundryAdapter  # noqa: E402
from owl_portability.adapters.servicenow import ServiceNowContextEngineAdapter  # noqa: E402

PROC = Namespace("http://enterprise.org/procurement#")

@pytest.fixture
def adapter() -> DataverseSemanticAdapter:
    """Dataverse adapter in simulation mode with procurement ontology."""
    return DataverseSemanticAdapter(
        ontology_path=str(ROOT / "ontologies" / "procurement.ttl"),
        shacl_path=str(ROOT / "ontologies" / "procurement_shacl.ttl"),
        simulation_mode=True,
    )

def _compliance_hold_query(
    *,
    approved_by: str | None = None,
    dataverse_context: dict | None = None,
    entity_class: str = "cr9a1_compliancehold",
    payload: dict | None = None,
) -> DataverseAgentQuery:
    base_payload: dict = {
        "cr9a1_paymentid": "PAY-TEST",
        "cr9a1_amountusd": 340000,
        "cr9a1_holdtype": "ComplianceHold",
    }
    if approved_by:
        base_payload["cr9a1_approvedby"] = approved_by
    if payload is not None:
        base_payload = payload
    return DataverseAgentQuery(
        query_id="dv-test",
        agent_id="test-agent",
        action_type="release_payment_hold",
        entity_class=entity_class,
        payload=base_payload,
        dataverse_context=dataverse_context
        if dataverse_context is not None
        else {"skill_applied": "PaymentApprovalWorkflow"},
    )

def test_empty_context_blocks_execution(adapter: DataverseSemanticAdapter) -> None:
    """Verifies that missing Dataverse semantic grounding prevents execution.

    Dataverse context is required — agents must be grounded before constraints
    are evaluated.
    """
    query = _compliance_hold_query(dataverse_context={})
    result = adapter.validate_dataverse_action(query)
    assert result.safe_to_execute is False
    assert result.dataverse_grounded is False
    assert result.shacl_valid is False

def test_compliance_hold_without_approver_blocked(
    adapter: DataverseSemanticAdapter,
) -> None:
    """Verifies that ComplianceHold release is blocked when holdApprovedBy is absent.

    This is the constraint that Dataverse's semantic layer understands (it knows
    this is a ComplianceHold) but cannot enforce (it cannot block the action).
    """
    result = adapter.validate_dataverse_action(_compliance_hold_query())
    assert result.shacl_valid is False
    assert result.safe_to_execute is False
    assert any("Legal approval" in v for v in result.violations)

def test_compliance_hold_with_approver_passes(adapter: DataverseSemanticAdapter) -> None:
    """Verifies that ComplianceHold release succeeds when both layers pass.

    Both Dataverse grounding and SHACL approval constraint must be satisfied.
    """
    result = adapter.validate_dataverse_action(
        _compliance_hold_query(approved_by="legal.reviewer@enterprise.com")
    )
    assert result.shacl_valid is True
    assert result.safe_to_execute is True

def test_dataverse_field_mapping(adapter: DataverseSemanticAdapter) -> None:
    """Verifies standard Dynamics 365 field names map to OWL properties.

    Enterprises use Dataverse with both custom (cr9a1_) and standard entity names.
    """
    query = DataverseAgentQuery(
        query_id="dv-field-map",
        agent_id="test-agent",
        action_type="create_payment",
        entity_class="invoice",
        payload={
            "totalamount": 75000,
            "paymentId": "PAY-D365-001",
        },
        dataverse_context={"resolved_table": "invoice"},
    )
    assert adapter.DATAVERSE_FIELD_MAP["totalamount"] == "amountUSD"
    graph = adapter._build_entity_rdf(
        query, adapter.DATAVERSE_TO_OWL_MAP["invoice"]
    )
    roots = list(graph.subjects(RDF.type, PROC.PaymentEvent))
    assert len(roots) == 1
    amounts = list(graph.objects(roots[0], PROC.amountUSD))
    assert len(amounts) == 1
    assert float(amounts[0]) == 75000.0

def test_dynamics365_entity_mapping(adapter: DataverseSemanticAdapter) -> None:
    """Verifies standard Dynamics 365 entities map to OWL classes.

    Enterprises often use standard Dynamics 365 entities alongside custom tables.
    """
    assert adapter.DATAVERSE_TO_OWL_MAP["account"] == "Vendor"
    assert adapter.DATAVERSE_TO_OWL_MAP["opportunity"] == "Contract"

    query = DataverseAgentQuery(
        query_id="dv-d365",
        agent_id="test-agent",
        action_type="update_vendor",
        entity_class="account",
        payload={"vendorId": "V-100"},
        dataverse_context={"resolved_table": "account"},
    )
    owl_class = adapter.DATAVERSE_TO_OWL_MAP.get(query.entity_class, query.entity_class)
    assert owl_class == "Vendor"

def test_write_simulation_mode(adapter: DataverseSemanticAdapter) -> None:
    """Verifies simulation mode works without credentials."""
    assert adapter.write({"paymentId": "P-1"}, "PaymentEvent") is True

def test_health_check_simulation(adapter: DataverseSemanticAdapter) -> None:
    """Verifies health check passes in simulation mode."""
    assert adapter.health_check() is True

def test_platform_name(adapter: DataverseSemanticAdapter) -> None:
    """Verifies platform identifier for routing decisions."""
    assert adapter.platform_name == "microsoft_dataverse"

def test_safe_to_execute_requires_both_layers() -> None:
    """Verifies AND logic: both grounding and SHACL must pass for execution.

    Neither layer alone is sufficient.
    """
    r1 = DataverseValidationResult(
        query_id="q1",
        agent_id="a1",
        action_type="act",
        dataverse_grounded=True,
        shacl_valid=False,
    )
    assert r1.safe_to_execute is False

    r2 = DataverseValidationResult(
        query_id="q2",
        agent_id="a2",
        action_type="act",
        dataverse_grounded=False,
        shacl_valid=True,
    )
    assert r2.safe_to_execute is False

    r3 = DataverseValidationResult(
        query_id="q3",
        agent_id="a3",
        action_type="act",
        dataverse_grounded=True,
        shacl_valid=True,
    )
    assert r3.safe_to_execute is True

def test_six_platform_demo_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Integration test verifying all six platform adapters instantiate together."""
    from owl_portability.adapters import palantir as palantir_module

    monkeypatch.setattr(
        palantir_module.PalantirFoundryAdapter,
        "health_check",
        lambda self: True,
    )

    adapters = [
        DataverseSemanticAdapter(
            ontology_path=str(ROOT / "ontologies" / "procurement.ttl"),
            shacl_path=str(ROOT / "ontologies" / "procurement_shacl.ttl"),
            simulation_mode=True,
        ),
        AgentCoreSemanticAdapter(
            ontology_path=str(ROOT / "ontologies" / "procurement.ttl"),
            shacl_path=str(ROOT / "ontologies" / "procurement_shacl.ttl"),
            simulation_mode=True,
        ),
        ServiceNowContextEngineAdapter(
            instance_url="https://example.service-now.com",
            username="demo",
            password="demo",
            simulation_mode=True,
        ),
        GoogleKnowledgeCatalogAdapter(project_id="demo-project"),
        FabricIQAdapter("ws", "ont", ""),
        PalantirFoundryAdapter(
            "https://example.palantirfoundry.com",
            "",
            {"PaymentEvent": "rid-1"},
        ),
    ]
    assert len(adapters) == 6
    for platform_adapter in adapters:
        assert platform_adapter.health_check() is True
