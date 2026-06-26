"""Grok-on-Databricks + OWL/SHACL governance demo.

Runs entirely in simulation_mode — zero API credentials required.

Part of the enterprise ontology governance stack.
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

from owl_portability.adapters.grok_databricks import (  # noqa: E402
    DatabricksAgentAction,
    DatabricksValidationResult,
    GrokDatabricksAdapter,
)


def _print_case(
    label: str,
    note: str,
    result: DatabricksValidationResult,
    detail: str | None,
) -> None:
    """Print a single test case in the Grok-on-Databricks governance format."""
    gateway = "✅ YES" if result.unity_gateway_permitted else "❌ NO"
    if not result.unity_gateway_permitted:
        shacl = "⏭️  SKIPPED"
    else:
        shacl = "✅ YES" if result.shacl_valid else "❌ NO"
    safe = "✅ EXECUTE" if result.safe_to_execute else "🚨 BLOCKED"

    print(label)
    print(f"   {note}")
    print()
    print(f"   Reasoning model:        {result.reasoning_model}")
    print(f"   Unity Gateway permitted: {gateway}")
    print(f"   SHACL valid:             {shacl}")
    print(f"   Safe to execute:         {safe}")
    if detail:
        print(f"   ↳ {detail}")
    print()


def main() -> None:
    print(
        "=================================================================\n"
        "GROK-ON-DATABRICKS + OWL/SHACL GOVERNANCE DEMO\n"
        "=================================================================\n"
        "\n"
        "Genie Ontology already ran:\n"
        "  ✅ Entity resolved: PAY-001 is a ComplianceHold\n"
        "  ✅ Business context: tied to payment + legal workflows\n"
        "  ✅ Query patterns indexed automatically\n"
        "\n"
        "Unity AI Gateway already ran:\n"
        "  ✅ Grok agent role permits Payment Release tool call\n"
        "\n"
        "Grok 4.3 reasoning:\n"
        "  ✅ Low hallucination rate, correctly interprets context\n"
        "\n"
        "OWL/SHACL constraint layer runs now:\n"
        "  ❓ Does this ComplianceHold have a recorded holdApprovedBy?\n"
    )

    adapter = GrokDatabricksAdapter(
        ontology_path=str(ROOT / "ontologies" / "procurement.ttl"),
        shacl_path=str(ROOT / "ontologies" / "procurement_shacl.ttl"),
        databricks_workspace_url="",
        databricks_token="",
        simulation_mode=True,
    )

    # Test 1 — Genie + Gateway pass, SHACL blocks (no Legal approver).
    result1 = adapter.validate_action(
        DatabricksAgentAction(
            action_id="gd-001",
            agent_identity="finance-analytics-agent@databricks",
            reasoning_model="grok-4.3",
            action_type="release_compliance_hold",
            entity_class="ComplianceHold",
            payload={
                "paymentId": "PAY-001",
                "amountUSD": 340000,
                "holdType": "ComplianceHold",
            },
            genie_context={
                "entity_type": "compliance_hold",
                "related_workflow": "legal_approval_workflow",
            },
            unity_gateway_permitted=True,
        )
    )
    _print_case(
        "🔴 Genie + Gateway PASS + SHACL BLOCKED — no Legal approver",
        "Grok understood the context completely. SHACL catches the gap.",
        result1,
        "ComplianceHold requires Legal approval before release.",
    )

    # Test 2 — All layers pass (Legal approval present).
    result2 = adapter.validate_action(
        DatabricksAgentAction(
            action_id="gd-002",
            agent_identity="legal-compliance-agent@databricks",
            reasoning_model="grok-4.3",
            action_type="release_compliance_hold",
            entity_class="ComplianceHold",
            payload={
                "paymentId": "PAY-001",
                "amountUSD": 340000,
                "holdType": "ComplianceHold",
                "approvedBy": "sarah.chen@legal.enterprise.com",
            },
            genie_context={
                "entity_type": "compliance_hold",
                "approval_status": "Legal sign-off recorded",
            },
            unity_gateway_permitted=True,
        )
    )
    _print_case(
        "🟢 All layers pass — Legal approval present",
        "Genie context, Gateway permission, and SHACL constraint validation all align.",
        result2,
        None,
    )

    # Test 3 — Unity AI Gateway denies, SHACL skipped.
    result3 = adapter.validate_action(
        DatabricksAgentAction(
            action_id="gd-003",
            agent_identity="readonly-analytics@databricks",
            reasoning_model="grok-4.3",
            action_type="release_compliance_hold",
            entity_class="ComplianceHold",
            payload={"paymentId": "PAY-002", "amountUSD": 50000},
            genie_context={"role": "read_only"},
            unity_gateway_permitted=False,
        )
    )
    _print_case(
        "⛔ Unity AI Gateway DENIED — SHACL skipped",
        "Unity AI Gateway denied this action. SHACL not invoked.",
        result3,
        None,
    )

    print(
        "=================================================================\n"
        "WHAT THIS DEMONSTRATES\n"
        "=================================================================\n"
        "\n"
        "  The reasoning model is swappable. Grok 4.3 today.\n"
        "  GPT-5 or Claude Opus tomorrow, if Databricks adds them.\n"
        "\n"
        "  The gap is not swappable. Genie Ontology gives context.\n"
        "  Unity AI Gateway gives access control.\n"
        "  Neither gives formal constraint proof.\n"
        "\n"
        "  Nine platforms now stress-tested.\n"
        "  Every reasoning model inherits the same architectural gap\n"
        "  from whichever data platform it's plugged into.\n"
        "\n"
        "  The model doesn't close the gap. The platform doesn't either.\n"
        "  The OWL/SHACL layer does.\n"
        "================================================================="
    )


if __name__ == "__main__":
    main()
