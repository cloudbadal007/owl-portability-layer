"""SHACL business rules for procurement (payments, holds, contracts)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import sys

SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from owl_portability.layer import OWLPortabilityLayer  # noqa: E402


@pytest.fixture
def layer(ontology_path: Path, shacl_path: Path) -> OWLPortabilityLayer:
    return OWLPortabilityLayer(ontology_path, shacl_path)


def test_valid_payment_passes(layer: OWLPortabilityLayer) -> None:
    """Routine payments with required paymentId and no conflicting holds pass."""
    data = {"paymentId": "P-OK", "amountUSD": 10_000}
    r = layer.validate_only(data, "PaymentEvent")
    assert r.passed is True
    assert r.violations == []


def test_compliance_hold_requires_approver(layer: OWLPortabilityLayer) -> None:
    """ComplianceHold must record holdApprovedBy (policy sign-off on the hold)."""
    data = {
        "paymentId": "P-CH",
        "amountUSD": 5_000,
        "hasHoldStatus": {"@type": "ComplianceHold"},
    }
    r = layer.validate_only(data, "PaymentEvent")
    assert r.passed is False
    assert any("Compliance holds must record" in v for v in r.violations)


def test_high_value_payment_with_hold_requires_payment_approver(
    layer: OWLPortabilityLayer,
) -> None:
    """Payments over $100k with an active hold must set holdApprovedBy on the payment."""
    data = {
        "paymentId": "P-HV",
        "amountUSD": 150_000,
        "hasHoldStatus": {"@type": "BudgetHold"},
    }
    r = layer.validate_only(data, "PaymentEvent")
    assert r.passed is False
    assert any("100,000" in v or "100000" in v or "$100" in v for v in r.violations)


def test_high_value_contract_requires_dual_approval(layer: OWLPortabilityLayer) -> None:
    """Contracts over $500k must set dualApprovalComplete to true."""
    data = {
        "contractValue": 600_000,
        "dualApprovalComplete": False,
    }
    r = layer.validate_only(data, "Contract")
    assert r.passed is False
    assert any("500" in v or "dualApproval" in v for v in r.violations)
