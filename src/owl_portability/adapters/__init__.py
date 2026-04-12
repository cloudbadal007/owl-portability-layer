"""Platform adapters: Palantir Foundry, Microsoft Fabric IQ, and generic MCP."""

from owl_portability.adapters.base import BaseAdapter
from owl_portability.adapters.fabric_iq import FabricIQAdapter
from owl_portability.adapters.mcp_adapter import MCPAdapter
from owl_portability.adapters.palantir import PalantirFoundryAdapter

__all__ = [
    "BaseAdapter",
    "FabricIQAdapter",
    "MCPAdapter",
    "PalantirFoundryAdapter",
]
