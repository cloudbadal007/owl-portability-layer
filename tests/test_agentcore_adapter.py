"""Tests for AWS AgentCore semantic adapter (Cedar vs OWL/SHACL).

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

from owl_portability.adapters.agentcore import (  # noqa: E402
    AgentCoreSemanticAdapter,
    AgentCoreToolCall,
)


@pytest.fixture
def adapter() -> AgentCoreSemanticAdapter:
    """AgentCore adapter in simulation mode with procurement ontology."""
    return AgentCoreSemanticAdapter(
        ontology_path=str(ROOT / "ontologies" / "procurement.ttl"),
        shacl_path=str(ROOT / "ontologies" / "procurement_shacl.ttl"),
        simulation_mode=True,
    )


def _release_hold_call(
    *,
    cedar_decision: str = "permit",
    approved_by: str | None = None,
    tool_name: str = "PaymentAPI__release_hold",
) -> AgentCoreToolCall:
    payload: dict = {
        "paymentId": "PAY-TEST",
        "amount": 340000,
        "holdType": "ComplianceHold",
    }
    if approved_by:
        payload["approvedBy"] = approved_by
    return AgentCoreToolCall(
        tool_call_id="tc-test",
        agent_identity_arn="arn:aws:bedrock-agentcore:us-east-1:1:agent/test",
        tool_name=tool_name,
        input_payload=payload,
        gateway_arn="arn:aws:bedrock-agentcore:us-east-1:1:gateway/gw",
        cedar_decision=cedar_decision,
        semantic_class="PaymentEvent",
    )


def test_cedar_deny_skips_shacl(adapter: AgentCoreSemanticAdapter) -> None:
    """Cedar deny short-circuits OWL/SHACL — access control is sufficient to block."""
    valid, violations = adapter.validate_tool_call(
        _release_hold_call(cedar_decision="deny")
    )
    assert valid is False
    assert violations == ["Cedar policy denied this tool call."]
    assert len(violations) == 1


def test_cedar_permit_with_shacl_block(adapter: AgentCoreSemanticAdapter) -> None:
    """Cedar permit does not imply domain validity — ComplianceHold needs Legal approval."""
    valid, violations = adapter.validate_tool_call(_release_hold_call())
    assert valid is False
    assert any("Legal approval" in v for v in violations)


def test_cedar_permit_with_shacl_valid(adapter: AgentCoreSemanticAdapter) -> None:
    """Both Cedar (permit) and OWL/SHACL (valid hold metadata) must pass for execution."""
    valid, violations = adapter.validate_tool_call(
        _release_hold_call(approved_by="legal.reviewer@enterprise.com")
    )
    assert valid is True
    assert violations == []


def test_unknown_tool_fails_closed(adapter: AgentCoreSemanticAdapter) -> None:
    """Unmapped tools fail closed — OWL/SHACL cannot validate unknown semantics."""
    call = _release_hold_call(tool_name="ShadowAPI__bypass_controls")
    valid, violations = adapter.validate_tool_call(call)
    assert valid is False
    assert len(violations) == 1
    assert "UNKNOWN TOOL" in violations[0]


def test_write_simulation_mode(adapter: AgentCoreSemanticAdapter) -> None:
    """Standard portability write path works in simulation without AWS credentials."""
    assert adapter.write({"paymentId": "P-1"}, "PaymentEvent") is True


def test_health_check_simulation(adapter: AgentCoreSemanticAdapter) -> None:
    """Health check succeeds offline when simulation_mode is enabled."""
    assert adapter.health_check() is True


def test_platform_name(adapter: AgentCoreSemanticAdapter) -> None:
    """Platform identifier is stable for routing and metrics."""
    assert adapter.platform_name == "aws_agentcore"


def test_log_semantic_decision_simulation(
    adapter: AgentCoreSemanticAdapter, capsys: pytest.CaptureFixture[str]
) -> None:
    """Structured decision logging works in simulation without raising."""
    call = _release_hold_call()
    adapter.log_semantic_decision(call, semantic_valid=False, violations=["test"])
    assert "final_decision" in capsys.readouterr().out


def test_read_simulation_mode(adapter: AgentCoreSemanticAdapter) -> None:
    """Read path returns simulation placeholder without AWS credentials."""
    records = adapter.read("PaymentEvent", {"paymentId": "PAY-1"})
    assert len(records) == 1
    assert records[0]["source"] == "agentcore"
    assert records[0]["simulation"] is True


def test_tool_to_owl_class_map_covers_release_hold() -> None:
    """Mapped tools resolve to procurement OWL classes for SHACL validation."""
    assert (
        AgentCoreSemanticAdapter.TOOL_TO_OWL_CLASS_MAP["PaymentAPI__release_hold"]
        == "PaymentEvent"
    )
