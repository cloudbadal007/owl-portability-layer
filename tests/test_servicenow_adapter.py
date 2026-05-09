"""Tests for ServiceNow Context Engine adapter.

Part of the OntoArc enterprise ontology toolkit.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from owl_portability.adapters.servicenow import ServiceNowContextEngineAdapter  # noqa: E402


def _adapter() -> ServiceNowContextEngineAdapter:
    return ServiceNowContextEngineAdapter(
        instance_url="https://example.service-now.com",
        username="user",
        password="pass",
        simulation_mode=True,
    )


def test_servicenow_adapter_simulation_write() -> None:
    adapter = _adapter()
    for owl_class in adapter.OWL_TO_TABLE_MAP:
        assert adapter.write({"id": "X-1"}, owl_class) is True


def test_servicenow_adapter_health_check_simulation() -> None:
    assert _adapter().health_check() is True


def test_servicenow_adapter_simulation_read() -> None:
    records = _adapter().read("PaymentEvent", {"payment_id": "PAY-1"})
    assert len(records) == 1
    assert records[0]["entity_class"] == "PaymentEvent"
    assert records[0]["source"] == "servicenow"
    assert records[0]["simulation"] is True


def test_servicenow_simulation_write_includes_owl_metadata(capsys) -> None:
    adapter = _adapter()
    assert adapter.write({"amount": 10, "approved": True}, "PaymentEvent") is True
    output = capsys.readouterr().out
    assert "u_owl_class" in output
    assert "u_owl_validated" in output
    assert "u_shacl_passed" in output
    assert "PaymentEvent" in output


def test_servicenow_unknown_class_defaults_to_generic_table() -> None:
    adapter = _adapter()
    assert adapter.write({"id": "X-2"}, "UnknownClass") is True
    assert adapter.OWL_TO_TABLE_MAP.get("UnknownClass", "u_owl_entity") == "u_owl_entity"


def test_servicenow_platform_name() -> None:
    assert _adapter().platform_name == "servicenow_context_engine"
