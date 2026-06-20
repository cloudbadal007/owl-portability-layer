"""Offline SHACL validation demo: valid payment vs two policy failures."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from owl_portability.layer import OWLPortabilityLayer  # noqa: E402


def main() -> None:
    onto = ROOT / "ontologies" / "procurement.ttl"
    shacl = ROOT / "ontologies" / "procurement_shacl.ttl"
    layer = OWLPortabilityLayer(onto, shacl)

    valid = {
        "paymentId": "PAY-OK-001",
        "amountUSD": 50_000,
    }
    r1 = layer.validate_only(valid, "PaymentEvent")
    print("--- Valid low-value payment (no hold) ---")
    print("[PASS]" if r1.passed else f"[FAIL] {r1.violations}")

    compliance_no_approver = {
        "paymentId": "PAY-BAD-CH-001",
        "amountUSD": 25_000,
        "hasHoldStatus": {
            "@type": "ComplianceHold",
        },
    }
    r2 = layer.validate_only(compliance_no_approver, "PaymentEvent")
    print("\n--- ComplianceHold without holdApprovedBy on hold (Rule 1) ---")
    print("[PASS]" if r2.passed else f"[FAIL] (expected) {r2.violations}")

    high_value_hold = {
        "paymentId": "PAY-BAD-HV-001",
        "amountUSD": 340_000,
        "hasHoldStatus": {"@type": "BudgetHold"},
    }
    r3 = layer.validate_only(high_value_hold, "PaymentEvent")
    print("\n--- High-value payment ($340K) on hold, no approver on payment (Rule 2) ---")
    print("[PASS]" if r3.passed else f"[FAIL] (expected) {r3.violations}")


if __name__ == "__main__":
    main()
