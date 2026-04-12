"""OWLPortabilityLayer integration tests."""

from __future__ import annotations

from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from owl_portability.adapters.palantir import PalantirFoundryAdapter  # noqa: E402
from owl_portability.layer import OWLPortabilityLayer  # noqa: E402


def test_validate_only_invalid_reports_violations(
    ontology_path: Path,
    shacl_path: Path,
) -> None:
    layer = OWLPortabilityLayer(ontology_path, shacl_path)
    r = layer.validate_only({}, "PaymentEvent")
    assert r.passed is False


def test_validate_and_route_unknown_platform(
    ontology_path: Path,
    shacl_path: Path,
) -> None:
    layer = OWLPortabilityLayer(ontology_path, shacl_path)
    r = layer.validate_and_route(
        {"paymentId": "X", "amountUSD": 1_000},
        "PaymentEvent",
        target_platform="missing",
    )
    assert r.passed is False
    assert any("No adapter" in v for v in r.violations)


def test_validate_and_route_with_adapter(
    ontology_path: Path,
    shacl_path: Path,
) -> None:
    layer = OWLPortabilityLayer(ontology_path, shacl_path)
    adapter = PalantirFoundryAdapter(
        "https://example.com",
        "",
        {"PaymentEvent": "rid"},
    )
    layer.register_adapter("palantir", adapter)
    r = layer.validate_and_route(
        {"paymentId": "X", "amountUSD": 1_000},
        "PaymentEvent",
        target_platform="palantir",
    )
    assert r.passed is True
