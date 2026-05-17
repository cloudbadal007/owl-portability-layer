"""Five-platform portability demo with identical SHACL governance.

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

from owl_portability.adapters.agentcore import AgentCoreSemanticAdapter  # noqa: E402
from owl_portability.adapters.fabric_iq import FabricIQAdapter  # noqa: E402
from owl_portability.adapters.google_knowledge_catalog import (  # noqa: E402
    GoogleKnowledgeCatalogAdapter,
)
from owl_portability.adapters.palantir import PalantirFoundryAdapter  # noqa: E402
from owl_portability.adapters.servicenow import ServiceNowContextEngineAdapter  # noqa: E402
from owl_portability.layer import OWLPortabilityLayer  # noqa: E402


def main() -> None:
    layer = OWLPortabilityLayer(
        ROOT / "ontologies" / "procurement.ttl",
        ROOT / "ontologies" / "procurement_shacl.ttl",
    )
    layer.register_adapter(
        "agentcore",
        AgentCoreSemanticAdapter(
            ontology_path=str(ROOT / "ontologies" / "procurement.ttl"),
            shacl_path=str(ROOT / "ontologies" / "procurement_shacl.ttl"),
            agentcore_region="us-east-1",
            simulation_mode=True,
        ),
    )
    layer.register_adapter(
        "servicenow",
        ServiceNowContextEngineAdapter(
            instance_url="https://example.service-now.com",
            username="demo",
            password="demo",
            simulation_mode=True,
        ),
    )
    layer.register_adapter("google", GoogleKnowledgeCatalogAdapter(project_id="demo-project"))
    layer.register_adapter(
        "microsoft",
        FabricIQAdapter(
            workspace_id="00000000-0000-0000-0000-000000000001",
            ontology_item_id="iq-ontology-1",
            token="",
        ),
    )
    layer.register_adapter(
        "palantir",
        PalantirFoundryAdapter(
            foundry_url="https://example.palantirfoundry.com",
            token="",
            object_type_map={"PaymentEvent": "ri.fake.palantir.object-type.payment"},
        ),
    )

    targets = [
        ("AgentCore", "agentcore"),
        ("ServiceNow", "servicenow"),
        ("Google", "google"),
        ("Microsoft", "microsoft"),
        ("Palantir", "palantir"),
    ]

    print("=== Test 1: Valid PaymentEvent across five platforms ===")
    valid_payload = {"paymentId": "PAY-5P-100", "amountUSD": 25000}
    for platform_name, key in targets:
        result = layer.validate_and_route(valid_payload, "PaymentEvent", target_platform=key)
        status = "✅" if result.passed else "🚨"
        print(f"{platform_name}: {status}")

    print("\n=== Test 2: ComplianceHold without approver blocked on all five ===")
    blocked_payload = {
        "paymentId": "PAY-5P-HOLD",
        "amountUSD": 150000,
        "hasHoldStatus": {"@type": "ComplianceHold"},
    }
    for platform_name, key in targets:
        result = layer.validate_and_route(blocked_payload, "PaymentEvent", target_platform=key)
        status = "✅" if result.passed else "🚨"
        print(f"{platform_name}: {status}")

    print(
        "\nFive platforms. One OWL/SHACL constraint layer.\n"
        "The SHACL constraint is identical across all five.\n"
        "Change target_platform. The governance never changes.\n"
        "\nPlatforms: AgentCore | ServiceNow | Google | Microsoft | Palantir"
    )


if __name__ == "__main__":
    main()
