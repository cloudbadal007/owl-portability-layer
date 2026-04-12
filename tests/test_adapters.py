"""Adapter simulation smoke tests (no live credentials)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from owl_portability.adapters.fabric_iq import FabricIQAdapter  # noqa: E402
from owl_portability.adapters.mcp_adapter import MCPAdapter, owl_class_to_tool_name  # noqa: E402
from owl_portability.adapters.palantir import PalantirFoundryAdapter  # noqa: E402


def test_palantir_write_simulation() -> None:
    a = PalantirFoundryAdapter(
        "https://invalid.local",
        "",
        {"PaymentEvent": "rid-1"},
    )
    assert a.write({"paymentId": "p"}, "PaymentEvent") is True


def test_fabric_write_simulation() -> None:
    a = FabricIQAdapter("ws", "ont", "")
    assert a.write({"x": 1}, "PaymentEvent") is True


def test_mcp_tool_name_mapping() -> None:
    assert owl_class_to_tool_name("PaymentEvent") == "ingest_payment_event"


def test_mcp_write_simulation() -> None:
    a = MCPAdapter("https://invalid.local")
    assert a.write({"paymentId": "p"}, "PaymentEvent") is True
