"""Tests for cross-platform offboarding validator.

Part of the OntoArc enterprise ontology toolkit.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from owl_portability.validators.offboarding_validator import (  # noqa: E402
    CrossPlatformOffboardingValidator,
    OffboardingEvent,
)


def _validator() -> CrossPlatformOffboardingValidator:
    return CrossPlatformOffboardingValidator(str(ROOT / "ontologies" / "employee_offboarding.ttl"))


def test_clean_offboarding_passes() -> None:
    event = OffboardingEvent(
        employee_id="EMP-4473",
        hr_status="resolved",
        it_status="resolved",
        finance_status="processed",
        ad_revoked=True,
        completion_certified=True,
        termination_date="2026-04-30",
    )
    conforms, violations = _validator().validate_offboarding(event)
    assert conforms is True
    assert violations == []
    assert event.severity == "none"


def test_ad_not_revoked_blocks_certification() -> None:
    event = OffboardingEvent(
        employee_id="EMP-4471",
        hr_status="resolved",
        it_status="resolved",
        finance_status="processed",
        ad_revoked=False,
        completion_certified=True,
        termination_date="2026-04-28",
    )
    conforms, violations = _validator().validate_offboarding(event)
    assert conforms is False
    assert any("🚨" in message for message in violations)
    assert event.severity == "critical"


def test_finance_before_hr_flagged() -> None:
    event = OffboardingEvent(
        employee_id="EMP-4472",
        hr_status="open",
        it_status="in_progress",
        finance_status="processed",
        ad_revoked=False,
        completion_certified=False,
        termination_date="2026-04-29",
    )
    conforms, violations = _validator().validate_offboarding(event)
    assert conforms is False
    assert any("⚠️" in message for message in violations)
    assert event.severity == "warning"


def test_missing_termination_date_flagged() -> None:
    event = OffboardingEvent(
        employee_id="EMP-9999",
        hr_status="resolved",
        it_status="resolved",
        finance_status="processed",
        ad_revoked=True,
        completion_certified=False,
    )
    conforms, violations = _validator().validate_offboarding(event)
    assert conforms is False
    assert any("⚠️ AUDIT RISK" in message for message in violations)
    assert event.severity == "warning"


def test_all_three_scenarios_in_report() -> None:
    validator = _validator()
    events = [
        OffboardingEvent(
            employee_id="EMP-4471",
            hr_status="resolved",
            it_status="resolved",
            finance_status="processed",
            ad_revoked=False,
            completion_certified=True,
            termination_date="2026-04-28",
        ),
        OffboardingEvent(
            employee_id="EMP-4472",
            hr_status="open",
            it_status="in_progress",
            finance_status="processed",
            ad_revoked=False,
            completion_certified=False,
            termination_date="2026-04-29",
        ),
        OffboardingEvent(
            employee_id="EMP-4473",
            hr_status="resolved",
            it_status="resolved",
            finance_status="processed",
            ad_revoked=True,
            completion_certified=True,
            termination_date="2026-04-30",
        ),
    ]
    for event in events:
        validator.validate_offboarding(event)
    report = validator.generate_report(events)
    assert "Total events: 3" in report
    assert "Clean: 1" in report
    assert "Flagged: 2" in report
    assert "Critical: 1" in report
    assert "Employee: EMP-4471" in report
    assert "Employee: EMP-4472" in report
    assert "Cross-platform offboarding report. Review all flagged events before certifying completion." in report


def test_validator_populates_event_violations_field() -> None:
    event = OffboardingEvent(
        employee_id="EMP-7777",
        hr_status="open",
        it_status="resolved",
        finance_status="processed",
        ad_revoked=False,
        completion_certified=True,
        termination_date="2026-05-01",
    )
    conforms, violations = _validator().validate_offboarding(event)
    assert conforms is False
    assert event.violations == violations
    assert event.severity in {"warning", "critical"}
