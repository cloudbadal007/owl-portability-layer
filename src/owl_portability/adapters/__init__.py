"""Platform adapters: Palantir Foundry, Microsoft Fabric IQ, AWS AgentCore, and MCP."""

from owl_portability.adapters.agentcore import AgentCoreSemanticAdapter, AgentCoreToolCall
from owl_portability.adapters.base import BaseAdapter
from owl_portability.adapters.fabric_iq import FabricIQAdapter
from owl_portability.adapters.google_knowledge_catalog import GoogleKnowledgeCatalogAdapter
from owl_portability.adapters.mcp_adapter import MCPAdapter
from owl_portability.adapters.palantir import PalantirFoundryAdapter
from owl_portability.adapters.servicenow import ServiceNowContextEngineAdapter

__all__ = [
    "AgentCoreSemanticAdapter",
    "AgentCoreToolCall",
    "BaseAdapter",
    "FabricIQAdapter",
    "GoogleKnowledgeCatalogAdapter",
    "MCPAdapter",
    "PalantirFoundryAdapter",
    "ServiceNowContextEngineAdapter",
]
