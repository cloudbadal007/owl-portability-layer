"""OpenAI Frontier + OWL/SHACL three-layer governance demo.

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

from owl_portability.adapters.openai_frontier import (  # noqa: E402
    FrontierAgentAction,
    FrontierValidationResult,
    OpenAIFrontierAdapter,
)


def _print_case(
    label: str,
    note: str,
    result: FrontierValidationResult,
    detail: str | None,
) -> None:
    """Print a single test case in the Frontier + OWL/SHACL governance format."""
    frontier = "✅ YES" if result.frontier_permitted else "❌ NO"
    if not result.frontier_permitted:
        shacl = "⏭️  SKIPPED"
    else:
        shacl = "✅ YES" if result.shacl_valid else "❌ NO"
    safe = "✅ EXECUTE" if result.safe_to_execute else "🚨 BLOCKED"

    print(label)
    print(f"   {note}")
    print()
    print(f"   Frontier permitted:  {frontier}")
    print(f"   SHACL valid:         {shacl}")
    print(f"   Safe to execute:     {safe}")
    if detail:
        print(f"   ↳ {detail}")
    print()


def main() -> None:
    print(
        "=================================================================\n"
        "OPENAI FRONTIER + OWL/SHACL THREE-LAYER GOVERNANCE DEMO\n"
        "=================================================================\n"
        "\n"
        "Frontier vs Google Knowledge Catalog vs Microsoft Fabric IQ:\n"
        "\n"
        "  Google:    Best open standards (RDF/JSON-LD) — retrieval focused\n"
        "  Microsoft: Closest to formal domain modelling — DirectLake bound\n"
        "  OpenAI:    Most accessible business context — \"AI co-worker\" model\n"
        "\n"
        "  All three: OWL ❌  SHACL ❌\n"
        "\n"
        "Frontier governance layers already ran:\n"
        "  ✅ Business Context: PAY-001 is a ComplianceHold\n"
        "  ✅ Workflow mapped: involves Legal Approval workflow\n"
        "  ✅ Agent identity verified\n"
        "  ✅ Permissions checked: within defined boundaries\n"
        "  ✅ Frontier decision: PERMITTED\n"
        "\n"
        "OWL/SHACL constraint layer runs now:\n"
        "  ❓ Does the ComplianceHold have a formal holdApprovedBy?\n"
    )

    adapter = OpenAIFrontierAdapter(
        ontology_path=str(ROOT / "ontologies" / "procurement.ttl"),
        shacl_path=str(ROOT / "ontologies" / "procurement_shacl.ttl"),
        frontier_api_key="",
        frontier_org_id="",
        simulation_mode=True,
    )

    # Test 1 — Frontier PERMITTED, SHACL BLOCKED (no Legal approver).
    result1 = adapter.validate_action(
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
                "related_agents": ["legal-agent", "finance-agent"],
            },
            frontier_permitted=True,
        )
    )
    _print_case(
        "🔴 Frontier PERMITTED + SHACL BLOCKED — Business Context ≠ Constraint Enforcement",
        "Frontier understood the ComplianceHold context completely.\n"
        "   OWL/SHACL caught what Business Context cannot enforce.",
        result1,
        "ComplianceHold requires Legal approval before release.",
    )

    # Test 2 — Both layers pass (Legal approval present).
    result2 = adapter.validate_action(
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
            frontier_context={
                "entity_type": "compliance_hold",
                "workflow": "legal_approval_workflow",
                "approval_status": "Legal sign-off recorded",
            },
            frontier_permitted=True,
        )
    )
    _print_case(
        "🟢 Frontier PERMITTED + SHACL VALID — all three layers pass",
        "Frontier permitted the action. OWL/SHACL validated the formal constraint.",
        result2,
        None,
    )

    # Test 3 — Frontier DENIED, SHACL skipped.
    result3 = adapter.validate_action(
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
    _print_case(
        "⛔ Frontier DENIED — SHACL skipped (Frontier denial sufficient)",
        "Frontier governance denied this action. SHACL not invoked.",
        result3,
        None,
    )

    print(
        "=================================================================\n"
        "THE THREE-LAYER GOVERNANCE MODEL\n"
        "=================================================================\n"
        "\n"
        "  Layer 1 — Frontier Business Context:\n"
        "    What does this entity mean in our organisation?\n"
        "    ✅ OpenAI ships this\n"
        "\n"
        "  Layer 2 — Frontier Identity + Permissions:\n"
        "    Who can call which action within defined boundaries?\n"
        "    ✅ OpenAI ships this\n"
        "\n"
        "  Layer 3 — OWL/SHACL Constraint Proof:\n"
        "    Are the formal domain constraints formally satisfied?\n"
        "    ❌ Yours to build\n"
        "\n"
        "  Test 1: Layers 1+2 passed. Layer 3 blocked. DENIED.\n"
        "  Test 2: All three layers passed. EXECUTED.\n"
        "  Test 3: Layer 2 denied. Layers 1+3 not invoked. DENIED.\n"
        "\n"
        "  OpenAI ships the understanding and the access control.\n"
        "  Build the formal constraint proof.\n"
        "  Pricing changes July 6 — build it before go-live.\n"
        "================================================================="
    )


if __name__ == "__main__":
    main()
