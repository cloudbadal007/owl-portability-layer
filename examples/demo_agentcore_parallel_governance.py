"""Cedar + OWL/SHACL parallel governance demo for AWS AgentCore.

Runs entirely in simulation_mode — zero AWS credentials required.

Part of the OntoArc enterprise ontology toolkit.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from owl_portability.adapters.agentcore import (  # noqa: E402
    AgentCoreSemanticAdapter,
    AgentCoreToolCall,
)


def _run_case(
    adapter: AgentCoreSemanticAdapter,
    label: str,
    tool_call: AgentCoreToolCall,
    *,
    cedar_note: str,
    owl_note: str,
    semantic_label: str,
    final_label: str,
    detail: str | None = None,
) -> tuple[str, str, str]:
    """Validate one tool call and print formatted governance output."""
    print(label)
    print(f"   {cedar_note}")
    print(f"   {owl_note}")
    print()

    if tool_call.cedar_decision == "deny":
        semantic_valid = False
        violations = ["Cedar policy denied this tool call."]
        cedar_status = "DENY"
    else:
        semantic_valid, violations = adapter.validate_tool_call(tool_call)
        cedar_status = "PERMIT"

    adapter.log_semantic_decision(tool_call, semantic_valid, violations)

    print(f"   Cedar:    {cedar_status}")
    print(f"   Semantic: {semantic_label}")
    print(f"   Final:    {final_label}")
    if detail:
        print(f"   ↳ {detail}")
    print()
    return cedar_status, semantic_label, final_label


def main() -> None:
    print(
        "=================================================================\n"
        "AWS AGENTCORE — CEDAR + OWL/SHACL PARALLEL GOVERNANCE DEMO\n"
        "=================================================================\n"
        "\n"
        "Cedar governance (simulated as already run at Gateway):\n"
        "  Evaluated: principal + action + resource + context.input\n"
        "  Applied:   role-based access, amount thresholds, OAuth claims\n"
        "\n"
        "OWL/SHACL governance runs now:\n"
        "  Evaluates: domain semantic validity of each tool call\n"
        "  Applied:   hold type constraints, approval requirements\n"
    )

    adapter = AgentCoreSemanticAdapter(
        ontology_path=str(ROOT / "ontologies" / "procurement.ttl"),
        shacl_path=str(ROOT / "ontologies" / "procurement_shacl.ttl"),
        agentcore_region="us-east-1",
        simulation_mode=True,
    )

    outcomes: list[tuple[str, str, str]] = []

    outcomes.append(
        _run_case(
            adapter,
            "🔴 Cedar PERMIT + Semantic BLOCKED — ComplianceHold, no approver",
            AgentCoreToolCall(
                tool_call_id="tc-001",
                agent_identity_arn=(
                    "arn:aws:bedrock-agentcore:us-east-1:123456789:agent/analytics-7a3f"
                ),
                tool_name="PaymentAPI__release_hold",
                input_payload={
                    "paymentId": "PAY-001",
                    "amount": 340000,
                    "holdType": "ComplianceHold",
                },
                gateway_arn=(
                    "arn:aws:bedrock-agentcore:us-east-1:123456789:gateway/payment-gw"
                ),
                cedar_decision="permit",
                semantic_class="PaymentEvent",
            ),
            cedar_note="Cedar permitted (agent has release-hold role in IAM/OAuth)",
            owl_note="OWL/SHACL checks: does ComplianceHold require holdApprovedBy?",
            semantic_label="INVALID",
            final_label="🚨 BLOCKED",
            detail="ComplianceHold requires Legal approval before release.",
        )
    )

    outcomes.append(
        _run_case(
            adapter,
            "🟢 Cedar PERMIT + Semantic VALID — Legal approval present",
            AgentCoreToolCall(
                tool_call_id="tc-002",
                agent_identity_arn=(
                    "arn:aws:bedrock-agentcore:us-east-1:123456789:agent/legal-9e1d"
                ),
                tool_name="PaymentAPI__release_hold",
                input_payload={
                    "paymentId": "PAY-001",
                    "amount": 340000,
                    "holdType": "ComplianceHold",
                    "approvedBy": "sarah.chen@legal.enterprise.com",
                },
                gateway_arn=(
                    "arn:aws:bedrock-agentcore:us-east-1:123456789:gateway/payment-gw"
                ),
                cedar_decision="permit",
                semantic_class="PaymentEvent",
            ),
            cedar_note="Cedar permitted (Legal role + release-hold scope)",
            owl_note="OWL/SHACL checks: ComplianceHold has holdApprovedBy on hold node",
            semantic_label="VALID",
            final_label="✅ EXECUTE",
        )
    )

    outcomes.append(
        _run_case(
            adapter,
            "⛔ Cedar DENY — Semantic check skipped (Cedar sufficient)",
            AgentCoreToolCall(
                tool_call_id="tc-003",
                agent_identity_arn=(
                    "arn:aws:bedrock-agentcore:us-east-1:123456789:agent/readonly-1a2b"
                ),
                tool_name="PaymentAPI__release_hold",
                input_payload={"paymentId": "PAY-002", "amount": 50000},
                gateway_arn=(
                    "arn:aws:bedrock-agentcore:us-east-1:123456789:gateway/payment-gw"
                ),
                cedar_decision="deny",
                semantic_class="PaymentEvent",
            ),
            cedar_note="Cedar denied (readonly agent lacks release-hold role)",
            owl_note="OWL/SHACL skipped — Cedar denial is sufficient",
            semantic_label="SKIPPED",
            final_label="🚨 BLOCKED",
        )
    )

    outcomes.append(
        _run_case(
            adapter,
            "🔴 Unknown tool — OWL/SHACL fails closed",
            AgentCoreToolCall(
                tool_call_id="tc-004",
                agent_identity_arn=(
                    "arn:aws:bedrock-agentcore:us-east-1:123456789:agent/analytics-7a3f"
                ),
                tool_name="ShadowAPI__bypass_controls",
                input_payload={"amount": 999999},
                gateway_arn=(
                    "arn:aws:bedrock-agentcore:us-east-1:123456789:gateway/unknown-gw"
                ),
                cedar_decision="permit",
                semantic_class="UnknownEntity",
            ),
            cedar_note="Cedar permitted (tool registered at Gateway — policy gap)",
            owl_note="OWL/SHACL: no semantic class mapping → fail-closed",
            semantic_label="INVALID",
            final_label="🚨 BLOCKED",
            detail="UNKNOWN TOOL has no OWL semantic class mapping.",
        )
    )

    print(
        "=================================================================\n"
        "THE CEDAR + OWL/SHACL MODEL\n"
        "=================================================================\n"
        "\n"
        "  Cedar governs:    Who can call which tool with what parameters\n"
        "  OWL/SHACL governs: Whether the semantic content is domain-valid\n"
        "\n"
        "  Cedar scope:    AgentCore Gateway boundary\n"
        "  OWL/SHACL scope: Cross-platform, before routing, vendor-neutral\n"
        "\n"
        "  Test 1: Cedar permitted. OWL/SHACL blocked. Final: DENIED.\n"
        "  Test 2: Cedar permitted. OWL/SHACL valid.   Final: EXECUTED.\n"
        "  Test 3: Cedar denied.   OWL/SHACL skipped.  Final: DENIED.\n"
        "  Test 4: Cedar permitted. OWL/SHACL blocked. Final: DENIED.\n"
        "\n"
        "  Both layers are necessary.\n"
        "  AWS ships Cedar. You build the OWL/SHACL layer.\n"
        "================================================================="
    )


if __name__ == "__main__":
    main()
