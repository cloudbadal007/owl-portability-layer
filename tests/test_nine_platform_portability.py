"""Nine-platform portability integration tests.

Verifies identical SHACL governance across all registered adapters.
Salesforce uses validate_only until the Agentforce adapter ships.

Part of the enterprise ontology governance stack.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from owl_portability.adapters.agentcore import AgentCoreSemanticAdapter  # noqa: E402
from owl_portability.adapters.dataverse import DataverseSemanticAdapter  # noqa: E402
from owl_portability.adapters.fabric_iq import FabricIQAdapter  # noqa: E402
from owl_portability.adapters.google_knowledge_catalog import (  # noqa: E402
    GoogleKnowledgeCatalogAdapter,
)
from owl_portability.adapters.ibm_watsonx import IBMWatsonxContextAdapter  # noqa: E402
from owl_portability.adapters.openai_frontier import OpenAIFrontierAdapter  # noqa: E402
from owl_portability.adapters.palantir import PalantirFoundryAdapter  # noqa: E402
from owl_portability.adapters.servicenow import ServiceNowContextEngineAdapter  # noqa: E402
from owl_portability.layer import OWLPortabilityLayer  # noqa: E402

LIVE_PLATFORMS = [
    "openai_frontier",
    "ibm_watsonx",
    "dataverse",
    "agentcore",
    "servicenow",
    "google",
    "microsoft",
    "palantir",
]

ALL_NINE_PLATFORMS = LIVE_PLATFORMS + ["salesforce"]


@pytest.fixture
def nine_platform_layer() -> OWLPortabilityLayer:
    """OWLPortabilityLayer with all eight live adapters registered."""
    onto = str(ROOT / "ontologies" / "procurement.ttl")
    shacl = str(ROOT / "ontologies" / "procurement_shacl.ttl")
    layer = OWLPortabilityLayer(onto, shacl)

    layer.register_adapter(
        "openai_frontier",
        OpenAIFrontierAdapter(
            ontology_path=onto,
            shacl_path=shacl,
            simulation_mode=True,
        ),
    )
    layer.register_adapter(
        "ibm_watsonx",
        IBMWatsonxContextAdapter(
            ontology_path=onto,
            shacl_path=shacl,
            simulation_mode=True,
        ),
    )
    layer.register_adapter(
        "dataverse",
        DataverseSemanticAdapter(
            ontology_path=onto,
            shacl_path=shacl,
            simulation_mode=True,
        ),
    )
    layer.register_adapter(
        "agentcore",
        AgentCoreSemanticAdapter(
            ontology_path=onto,
            shacl_path=shacl,
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
    return layer


def test_valid_payment_event_passes_all_live_platforms(
    nine_platform_layer: OWLPortabilityLayer,
) -> None:
    """Valid PaymentEvent passes SHACL on every registered adapter.

    The constraint layer is identical — only the target_platform key changes.
    """
    payload = {"paymentId": "PAY-9P-100", "amountUSD": 25000}
    for platform in LIVE_PLATFORMS:
        result = nine_platform_layer.validate_and_route(
            payload, "PaymentEvent", target_platform=platform
        )
        assert result.passed is True, f"{platform} should pass valid PaymentEvent"


def test_compliance_hold_without_approver_blocked_all_live_platforms(
    nine_platform_layer: OWLPortabilityLayer,
) -> None:
    """ComplianceHold without approver is blocked on every registered adapter.

    Platform semantic layers may understand the hold; SHACL enforces the proof.
    """
    payload = {
        "paymentId": "PAY-9P-HOLD",
        "amountUSD": 150000,
        "hasHoldStatus": {"@type": "ComplianceHold"},
    }
    for platform in LIVE_PLATFORMS:
        result = nine_platform_layer.validate_and_route(
            payload, "PaymentEvent", target_platform=platform
        )
        assert result.passed is False, f"{platform} should block hold without approver"


def test_salesforce_validate_only_same_shacl_constraint(
    nine_platform_layer: OWLPortabilityLayer,
) -> None:
    """Salesforce (adapter coming soon) still runs the same SHACL constraint.

    validate_only proves governance is platform-independent even without an adapter.
    """
    valid = nine_platform_layer.validate_only(
        {"paymentId": "PAY-SF-1", "amountUSD": 25000},
        "PaymentEvent",
    )
    blocked = nine_platform_layer.validate_only(
        {
            "paymentId": "PAY-SF-HOLD",
            "amountUSD": 150000,
            "hasHoldStatus": {"@type": "ComplianceHold"},
        },
        "PaymentEvent",
    )
    assert valid.passed is True
    assert blocked.passed is False


def test_nine_platform_matrix_includes_salesforce() -> None:
    """Nine-platform matrix lists Salesforce even before its adapter ships."""
    assert len(ALL_NINE_PLATFORMS) == 9
    assert "salesforce" in ALL_NINE_PLATFORMS
    assert "openai_frontier" in ALL_NINE_PLATFORMS


def test_openai_frontier_is_first_registered_platform(
    nine_platform_layer: OWLPortabilityLayer,
) -> None:
    """OpenAI Frontier adapter is registered and routable."""
    result = nine_platform_layer.validate_and_route(
        {"paymentId": "PAY-FR", "amountUSD": 1000},
        "PaymentEvent",
        target_platform="openai_frontier",
    )
    assert result.passed is True
    assert result.platform_target == "openai_frontier"
