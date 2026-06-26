"""Nine-platform portability integration tests.

Verifies identical SHACL governance across all nine registered adapters.

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
from owl_portability.adapters.grok_databricks import GrokDatabricksAdapter  # noqa: E402
from owl_portability.adapters.ibm_watsonx import IBMWatsonxContextAdapter  # noqa: E402
from owl_portability.adapters.openai_frontier import OpenAIFrontierAdapter  # noqa: E402
from owl_portability.adapters.palantir import PalantirFoundryAdapter  # noqa: E402
from owl_portability.adapters.servicenow import ServiceNowContextEngineAdapter  # noqa: E402
from owl_portability.layer import OWLPortabilityLayer  # noqa: E402

LIVE_PLATFORMS = [
    "grok_databricks",
    "openai_frontier",
    "ibm_watsonx",
    "dataverse",
    "agentcore",
    "servicenow",
    "google",
    "microsoft",
    "palantir",
]


@pytest.fixture
def nine_platform_layer() -> OWLPortabilityLayer:
    """OWLPortabilityLayer with all nine live adapters registered."""
    onto = str(ROOT / "ontologies" / "procurement.ttl")
    shacl = str(ROOT / "ontologies" / "procurement_shacl.ttl")
    layer = OWLPortabilityLayer(onto, shacl)

    layer.register_adapter(
        "grok_databricks",
        GrokDatabricksAdapter(
            ontology_path=onto,
            shacl_path=shacl,
            simulation_mode=True,
        ),
    )
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


def test_nine_platform_matrix_has_nine_live_adapters() -> None:
    """Nine-platform matrix lists exactly nine routable adapter keys."""
    assert len(LIVE_PLATFORMS) == 9
    assert "grok_databricks" in LIVE_PLATFORMS
    assert "openai_frontier" in LIVE_PLATFORMS
    assert "palantir" in LIVE_PLATFORMS


def test_grok_databricks_is_registered_platform(
    nine_platform_layer: OWLPortabilityLayer,
) -> None:
    """Grok-on-Databricks adapter is registered and routable."""
    result = nine_platform_layer.validate_and_route(
        {"paymentId": "PAY-GD", "amountUSD": 1000},
        "PaymentEvent",
        target_platform="grok_databricks",
    )
    assert result.passed is True
    assert result.platform_target == "grok_databricks"
