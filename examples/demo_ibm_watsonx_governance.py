"""IBM watsonx.data Context + OWL/SHACL parallel governance demo.

Runs entirely in simulation_mode — zero IBM credentials required.

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

from owl_portability.adapters.ibm_watsonx import (  # noqa: E402
    IBMWatsonxContextAdapter,
    WatsonxContextQuery,
    WatsonxValidationResult,
)


def _print_case(
    label: str,
    note: str,
    result: WatsonxValidationResult,
    detail: str | None,
) -> None:
    """Print a single test case in the IBM + OWL/SHACL governance format."""
    ibm = "PERMIT" if result.ibm_governance == "permit" else "DENY"
    shacl = "✅ YES" if result.shacl_valid else "❌ NO"
    if result.ibm_governance == "deny":
        shacl = "⏭️  SKIPPED"
    safe = "✅ EXECUTE" if result.safe_to_execute else "🚨 BLOCKED"

    print(label)
    print(f"   {note}")
    print()
    print(f"   IBM governance:  {ibm}")
    print(f"   SHACL valid:     {shacl}")
    print(f"   Safe to execute: {safe}")
    if detail:
        print(f"   ↳ {detail}")
    print()


def main() -> None:
    print(
        "=================================================================\n"
        "IBM WATSONX.DATA CONTEXT + OWL/SHACL GOVERNANCE DEMO\n"
        "=================================================================\n"
        "\n"
        "IBM vs Google Knowledge Catalog vs AWS AgentCore:\n"
        "  Google:  Best open standards (RDF/JSON-LD) — retrieval focused\n"
        "  AWS:     Best governance authoring (Cedar) — gateway scoped\n"
        "  IBM:     Federated + runtime governance claim — closest to SHACL\n"
        "\n"
        "IBM watsonx.data Context already ran:\n"
        "  ✅ Semantic meaning applied to entity\n"
        "  ✅ Runtime policy governance evaluated\n"
        "  ✅ Federated context graph resolved\n"
        "  ✅ IBM governance decision: PERMIT (policy check passed)\n"
        "\n"
        "OWL/SHACL constraint layer runs now:\n"
        "  ❓ Does the formal domain constraint catch what IBM's policy missed?\n"
    )

    adapter = IBMWatsonxContextAdapter(
        ontology_path=str(ROOT / "ontologies" / "procurement.ttl"),
        shacl_path=str(ROOT / "ontologies" / "procurement_shacl.ttl"),
        watsonx_url="https://your-instance.cloud.ibm.com",
        simulation_mode=True,
    )

    # Test 1 — IBM permits, SHACL blocks (ComplianceHold no approver).
    result1 = adapter.validate_with_shacl(
        WatsonxContextQuery(
            query_id="wx-001",
            agent_id="watsonx-finance-agent",
            action_type="release_compliance_hold",
            entity_class="ComplianceHold",
            payload={
                "paymentId": "PAY-001",
                "amountUSD": 340000,
                "holdType": "ComplianceHold",
            },
            watsonx_context={
                "entity_type": "compliance_hold",
                "federated_source": "ibm-cloud-us-south",
                "semantic_class": "ComplianceHold",
                "governance_policy": "payment_release_policy_v2",
            },
            ibm_governance_decision="permit",
            watsonx_semantic_class="ComplianceHold",
        )
    )
    _print_case(
        "🔴 IBM PERMIT + SHACL BLOCKED — policy vs proof gap",
        "IBM's runtime policy passed. SHACL catches the formal gap.",
        result1,
        "ComplianceHold requires Legal approval before release.",
    )

    # Test 2 — Both layers pass (ComplianceHold with approver).
    result2 = adapter.validate_with_shacl(
        WatsonxContextQuery(
            query_id="wx-002",
            agent_id="watsonx-legal-agent",
            action_type="release_compliance_hold",
            entity_class="ComplianceHold",
            payload={
                "paymentId": "PAY-001",
                "amountUSD": 340000,
                "holdType": "ComplianceHold",
                "approvedBy": "sarah.chen@legal.enterprise.com",
            },
            watsonx_context={
                "entity_type": "compliance_hold",
                "federated_source": "ibm-cloud-us-south",
                "approval_status": "Legal sign-off recorded",
            },
            ibm_governance_decision="permit",
            watsonx_semantic_class="ComplianceHold",
        )
    )
    _print_case(
        "🟢 IBM PERMIT + SHACL VALID — both layers pass",
        "IBM permitted the action. SHACL validated the formal constraint.",
        result2,
        None,
    )

    # Test 3 — IBM denies, SHACL skipped.
    result3 = adapter.validate_with_shacl(
        WatsonxContextQuery(
            query_id="wx-003",
            agent_id="watsonx-analytics-agent",
            action_type="release_compliance_hold",
            entity_class="ComplianceHold",
            payload={"paymentId": "PAY-002", "amountUSD": 50000},
            watsonx_context={"governance_policy": "analytics_read_only"},
            ibm_governance_decision="deny",
            watsonx_semantic_class="ComplianceHold",
        )
    )
    _print_case(
        "⛔ IBM DENY — SHACL skipped (IBM denial sufficient)",
        "IBM watsonx.data Context denied this action. SHACL not invoked.",
        result3,
        None,
    )

    # Test 4 — Cross-platform gap illustration.
    result4 = adapter.validate_with_shacl(
        WatsonxContextQuery(
            query_id="wx-004",
            agent_id="external-salesforce-agent",
            action_type="release_compliance_hold",
            entity_class="ComplianceHold",
            payload={
                "paymentId": "PAY-003",
                "amountUSD": 847000,
                "holdType": "ComplianceHold",
            },
            watsonx_context={},
            ibm_governance_decision="permit",
            watsonx_semantic_class="ComplianceHold",
        )
    )
    _print_case(
        "🔴 CROSS-PLATFORM GAP — IBM Gateway bypassed, SHACL catches",
        "IBM couldn't resolve the external agent. SHACL still blocks.",
        result4,
        "ComplianceHold requires Legal approval before release.",
    )

    print(
        "=================================================================\n"
        "IBM vs GOOGLE vs AWS — THE THREE-WAY VERDICT\n"
        "=================================================================\n"
        "\n"
        "  Google Knowledge Catalog:\n"
        "    ✅ Best open standards (RDF/JSON-LD)\n"
        "    ✅ Best semantic retrieval at scale\n"
        "    ❌ No formal constraint enforcement\n"
        "    ❌ OWL ❌ SHACL\n"
        "\n"
        "  AWS AgentCore (Cedar):\n"
        "    ✅ Best governance authoring (Cedar)\n"
        "    ✅ Formally verifiable policy language\n"
        "    ⚠️  Gateway-scope only\n"
        "    ❌ OWL ❌ SHACL\n"
        "\n"
        "  IBM watsonx.data Context:\n"
        "    ✅ Federated + cross-cloud architecture\n"
        "    ✅ Runtime governance enforcement claimed\n"
        "    ✅ Open standards alignment claimed\n"
        "    ⚠️  Policy-based, not formally provable\n"
        "    ⚠️  Private preview — production pending\n"
        "    ❌ OWL ❌ SHACL\n"
        "\n"
        "  All three: excellent semantic understanding.\n"
        "  None:      formal OWL/SHACL constraint proof.\n"
        "\n"
        "  IBM enforces policies. OWL/SHACL enforces proofs.\n"
        "  Build the proofs.\n"
        "================================================================="
    )


if __name__ == "__main__":
    main()
