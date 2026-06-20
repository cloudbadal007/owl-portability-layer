"""Route validated entities to any MCP server via JSON-RPC 2.0 (vendor-free path)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from owl_portability.adapters.base import BaseAdapter

logger = logging.getLogger(__name__)


def owl_class_to_tool_name(entity_class: str) -> str:
    """Map OWL class local names to MCP tool identifiers (snake_case)."""
    # PaymentEvent -> ingest_payment_event
    s = "".join(["_" + c.lower() if c.isupper() else c for c in entity_class]).lstrip("_")
    return f"ingest_{s}"


class MCPAdapter(BaseAdapter):
    """POST validated payloads to an MCP server as JSON-RPC ``tools/call`` requests.

    No Palantir or Fabric dependency—ideal for agent meshes and self-healing MCP
    patterns: the same SHACL gate feeds tools that repair or escalate on failure.

    Example wiring (conceptual)::

        # After validation, MCP tool ``ingest_payment_event`` runs in a server that
        # retries on 5xx or raises a ticket—OWL classes map 1:1 to tool names.
        layer.register_adapter("mcp", MCPAdapter("http://localhost:8080/mcp"))
        layer.validate_and_route(payload, "PaymentEvent", target_platform="mcp")
    """

    def __init__(self, mcp_server_url: str) -> None:
        """Store MCP HTTP endpoint (Streamable HTTP or gateway wrapping stdio server).

        Args:
            mcp_server_url: Base URL for JSON-RPC calls (e.g. ``http://127.0.0.1:8765/rpc``).
        """
        self._url = mcp_server_url.rstrip("/")

    @property
    def platform_name(self) -> str:
        return "mcp"

    def write(self, entity_data: dict[str, Any], entity_class: str) -> bool:
        tool = owl_class_to_tool_name(entity_class)
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": entity_data},
        }
        rpc_url = f"{self._url}" if self._url.endswith("/rpc") else f"{self._url}/rpc"
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.post(rpc_url, json=body, headers={"Content-Type": "application/json"})
            logger.info("MCP JSON-RPC tools/call: tool=%s status=%s", tool, r.status_code)
            if r.status_code >= 400:
                return False
        except httpx.HTTPError as exc:
            logger.info("MCP call (offline or unreachable): %s", exc)
        return True

    def read(self, entity_class: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        tool = f"query_{owl_class_to_tool_name(entity_class).removeprefix('ingest_')}"
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": filters},
        }
        rpc_url = f"{self._url}" if self._url.endswith("/rpc") else f"{self._url}/rpc"
        try:
            with httpx.Client(timeout=15.0) as client:
                r = client.post(rpc_url, json=body, headers={"Content-Type": "application/json"})
            logger.info("MCP JSON-RPC query: tool=%s status=%s", tool, r.status_code)
        except httpx.HTTPError as exc:
            logger.info("MCP query (offline): %s", exc)
        return []

    def health_check(self) -> bool:
        url = f"{self._url}/health" if not self._url.endswith("/rpc") else self._url.replace("/rpc", "/health")
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.get(url)
            return r.status_code < 500
        except httpx.HTTPError:
            return False
