"""Cross-platform offboarding validation demo (offline only).

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


def main() -> None:
    validator = CrossPlatformOffboardingValidator(
        str(ROOT / "ontologies" / "employee_offboarding.ttl")
    )

    scenarios: list[tuple[str, str, OffboardingEvent]] = [
        (
            "🔴 SCENARIO 1: Incomplete — AD still active",
            "blocked",
            OffboardingEvent(
                employee_id="EMP-4471",
                hr_status="resolved",
                it_status="resolved",
                finance_status="processed",
                ad_revoked=False,
                completion_certified=True,
                termination_date="2026-04-28",
            ),
        ),
        (
            "🔴 SCENARIO 2: Finance before HR",
            "flagged",
            OffboardingEvent(
                employee_id="EMP-4472",
                hr_status="open",
                it_status="in_progress",
                finance_status="processed",
                ad_revoked=False,
                completion_certified=False,
                termination_date="2026-04-29",
            ),
        ),
        (
            "🟢 SCENARIO 3: Clean offboarding",
            "approved",
            OffboardingEvent(
                employee_id="EMP-4473",
                hr_status="resolved",
                it_status="resolved",
                finance_status="processed",
                ad_revoked=True,
                completion_certified=True,
                termination_date="2026-04-30",
            ),
        ),
    ]

    approved = 0
    flagged = 0
    blocked = 0

    print("=================================================================")
    print("CROSS-PLATFORM OFFBOARDING VALIDATION DEMO")
    print("=================================================================\n")

    for title, expected, event in scenarios:
        conforms, violations = validator.validate_offboarding(event)
        print(title)
        if conforms:
            print("   Result: ✅ OFFBOARDING CERTIFIED COMPLETE\n")
            approved += 1
            continue

        if event.severity == "critical":
            print("   Result: 🚨 BLOCKED")
            blocked += 1
        else:
            print("   Result: ⚠️  FLAGGED")
            flagged += 1
        first_violation = violations[0] if violations else "Validation failed without report text."
        print(f"   ↳ {first_violation}\n")

        # Keep the expected classification visible for demo readers.
        _ = expected

    print("=================================================================")
    print("SUMMARY")
    print(f"Total: 3 | Approved: {approved} | Flagged: {flagged} | Blocked: {blocked}")
    print("=================================================================")


if __name__ == "__main__":
    main()
