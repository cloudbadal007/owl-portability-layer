"""Microsoft Dataverse + OWL/SHACL bridge demo.

Runs entirely in simulation_mode — zero Dataverse credentials required.
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

from owl_portability.adapters.dataverse import (  # noqa: E402
    DataverseAgentQuery,
    DataverseSemanticAdapter,
)

def _print_result(label: str, result, *, context_line: str, detail: str | None = None) -> str:
    """Print formatted two-layer validation output and return outcome token."""
    grounded_icon = "✅ YES" if result.dataverse_grounded else "❌ NO"
    shacl_icon = "✅ YES" if result.shacl_valid else "❌ NO"
    safe_icon = "✅ EXECUTE" if result.safe_to_execute else "🚨 BLOCKED"

    print(label)
    print(f"   {context_line}")
    print()
    print(f"   Dataverse grounded:  {grounded_icon}")
    print(f"   SHACL valid:         {shacl_icon}")
    print(f"   Safe to execute:     {safe_icon}")
    if detail:
        print(f"   ↳ {detail}")
    print()

    if result.safe_to_execute:
        return "EXECUTED"
    return "DENIED"

def main() -> None:
    print(
        "=================================================================\n"
        "MICROSOFT DATAVERSE + OWL/SHACL BRIDGE DEMO\n"
        "=================================================================\n"
        "\n"
        "Dataverse semantic layer already ran:\n"
        "  ✅ Schema graph traversed — relevant tables identified\n"
        "  ✅ Business Skills applied — approval workflow context loaded\n"
        "  ✅ MCP Server queried — entity relationships resolved\n"
        "  ✅ Semantic search complete — PAY-001 is a ComplianceHold\n"
        "\n"
        "OWL/SHACL constraint layer runs now:\n"
        "  ❓ Is this action formally valid given domain constraints?\n"
    )

    adapter = DataverseSemanticAdapter(
        ontology_path=str(ROOT / "ontologies" / "procurement.ttl"),
        shacl_path=str(ROOT / "ontologies" / "procurement_shacl.ttl"),
        dataverse_url="https://yourorg.crm.dynamics.com",
        simulation_mode=True,
    )

    test1 = DataverseAgentQuery(
        query_id="dv-001",
        agent_id="copilot-finance-agent",
        action_type="release_payment_hold",
        entity_class="cr9a1_compliancehold",
        payload={
            "cr9a1_paymentid": "PAY-001",
            "cr9a1_amountusd": 340000,
            "cr9a1_holdtype": "ComplianceHold",
        },
        dataverse_context={
            "resolved_table": "cr9a1_paymentevent",
            "skill_applied": "PaymentApprovalWorkflow",
            "related_entities": ["cr9a1_vendor", "cr9a1_contract"],
            "business_rule": "ComplianceHold requires Legal sign-off",
        },
        skill_applied="PaymentApprovalWorkflow",
    )
    r1 = adapter.validate_dataverse_action(test1)
    outcome1 = _print_result(
        "🔴 Dataverse GROUNDED + SHACL BLOCKED — no Legal approver",
        r1,
        context_line="Dataverse understood context. OWL/SHACL blocks the action.",
        detail="ComplianceHold requires Legal approval before release.",
    )

    test2 = DataverseAgentQuery(
        query_id="dv-002",
        agent_id="copilot-legal-agent",
        action_type="release_payment_hold",
        entity_class="cr9a1_compliancehold",
        payload={
            "cr9a1_paymentid": "PAY-001",
            "cr9a1_amountusd": 340000,
            "cr9a1_holdtype": "ComplianceHold",
            "cr9a1_approvedby": "sarah.chen@legal.enterprise.com",
        },
        dataverse_context={
            "resolved_table": "cr9a1_paymentevent",
            "skill_applied": "PaymentApprovalWorkflow",
            "approval_status": "Legal sign-off recorded",
        },
        skill_applied="PaymentApprovalWorkflow",
    )
    r2 = adapter.validate_dataverse_action(test2)
    outcome2 = _print_result(
        "🟢 Dataverse GROUNDED + SHACL VALID — both layers pass",
        r2,
        context_line="Both layers passed. Action is authorised.",
    )

    test3 = DataverseAgentQuery(
        query_id="dv-003",
        agent_id="copilot-analytics-agent",
        action_type="release_payment_hold",
        entity_class="cr9a1_paymentevent",
        payload={"amount": 50000},
        dataverse_context={},
    )
    r3 = adapter.validate_dataverse_action(test3)
    outcome3 = _print_result(
        "🔴 Dataverse GROUNDING FAILED — no context returned",
        r3,
        context_line="Semantic grounding failed. Constraints not evaluated.",
        detail=r3.violations[0] if r3.violations else None,
    )

    print(
        "=================================================================\n"
        "THE DATAVERSE + OWL/SHACL MODEL\n"
        "=================================================================\n"
        "\n"
        "  Dataverse provides:  Business understanding\n"
        "    - Schema graph traversal\n"
        "    - Business Skills (procedural knowledge)\n"
        "    - MCP Server for dynamic schema discovery\n"
        "\n"
        "  OWL/SHACL provides:  Formal constraint enforcement\n"
        "    - Hold type class hierarchy\n"
        "    - Approval requirements\n"
        "    - Value thresholds\n"
        "    - Cross-platform portability\n"
        "\n"
        f"  Test 1: Dataverse grounded. OWL/SHACL blocked. {outcome1}.\n"
        f"  Test 2: Both layers passed. {outcome2}.\n"
        f"  Test 3: Dataverse failed. Both blocked. {outcome3}.\n"
        "\n"
        "  Understanding ≠ Permission.\n"
        "  Microsoft ships the understanding.\n"
        "  Build the governance.\n"
        "================================================================="
    )

if __name__ == "__main__":
    main()
