"""Same validated entity, different platform — one config key changes."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from owl_portability.adapters.fabric_iq import FabricIQAdapter  # noqa: E402
from owl_portability.adapters.palantir import PalantirFoundryAdapter  # noqa: E402
from owl_portability.layer import OWLPortabilityLayer  # noqa: E402


def main() -> None:
    onto = ROOT / "ontologies" / "procurement.ttl"
    shacl = ROOT / "ontologies" / "procurement_shacl.ttl"
    layer = OWLPortabilityLayer(onto, shacl)

    palantir = PalantirFoundryAdapter(
        foundry_url="https://example.palantirfoundry.com",
        token="",
        object_type_map={"PaymentEvent": "ri.fake.palantir.object-type.payment"},
    )
    fabric = FabricIQAdapter(
        workspace_id="00000000-0000-0000-0000-000000000001",
        ontology_item_id="iq-ontology-1",
        token="",
    )
    layer.register_adapter("palantir", palantir)
    layer.register_adapter("fabric_iq", fabric)

    payload = {"paymentId": "PAY-PORT-1", "amountUSD": 42_000}

    print("=== Business logic identical; only target_platform changes ===\n")
    rp = layer.validate_and_route(payload, "PaymentEvent", target_platform="palantir")
    print(f"Route -> Palantir: passed={rp.passed} violations={rp.violations}")

    rf = layer.validate_and_route(payload, "PaymentEvent", target_platform="fabric_iq")
    print(f"Route -> Fabric IQ: passed={rf.passed} violations={rf.violations}")

    print(
        "\nOne-line switch: validate_and_route(..., target_platform='fabric_iq') "
        "vs target_platform='palantir'."
    )


if __name__ == "__main__":
    main()
