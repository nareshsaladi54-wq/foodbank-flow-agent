"""MCP-backed access to FoodBankFlow's data sources.

Replaces tools.py's earlier direct calls to core.load_inventory/load_families/
load_intake (still present and unchanged - run_demo.py and the tests use
them directly, so the offline demo and the deterministic test suite stay
network-free). The live agent instead reaches this same data through the
Model Context Protocol, via mcp_server.py.

By default the MCP server is spawned as a stdio subprocess - no separate
deployment needed, works the same locally and inside the AgentCore Runtime
container. Set MCP_DATA_SERVER_URL to a streamable-HTTP MCP server's URL to
point at a real backend instead; nothing else in this file or its callers
needs to change.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import uuid

from mcp import StdioServerParameters, stdio_client
from strands.tools.mcp import MCPClient

MCP_DATA_SERVER_URL = os.environ.get("MCP_DATA_SERVER_URL")

_client: MCPClient | None = None
_client_lock = threading.Lock()


def _build_client() -> MCPClient:
    if MCP_DATA_SERVER_URL:
        return MCPClient(url=MCP_DATA_SERVER_URL)
    params = StdioServerParameters(command=sys.executable, args=["-m", "foodbankflow.mcp_server"])
    return MCPClient(lambda: stdio_client(params))


def _session() -> MCPClient:
    """Lazily start the shared MCP client. Strands can execute tool calls
    concurrently, so this must not let a second thread observe `_client`
    assigned-but-not-yet-started - hence the lock, and only publishing
    `_client` after start() (which blocks until the session is live) returns."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                client = _build_client()
                client.start()
                _client = client
    return _client


def _call(tool_name: str):
    result = _session().call_tool_sync(str(uuid.uuid4()), tool_name)
    if result["status"] != "success":
        raise RuntimeError(f"MCP tool {tool_name!r} failed: {result}")
    structured = result.get("structuredContent")
    # FastMCP wraps a non-object return (e.g. our list[dict] tools) as
    # {"result": <value>} per the MCP output-schema convention; a dict
    # return (get_families) comes back as the structured content itself.
    if isinstance(structured, dict) and set(structured) == {"result"}:
        return structured["result"]
    if structured is not None:
        return structured
    return json.loads(result["content"][0]["text"])


def get_inventory() -> list[dict]:
    """Current stock on hand, via the foodbankflow-data MCP server."""
    return _call("get_inventory")


def get_families() -> dict:
    """Registered families and the allocation policy, via the foodbankflow-data MCP server."""
    return _call("get_families")


def get_intake_queue() -> list[dict]:
    """Pending donations from the intake queue, via the foodbankflow-data MCP server."""
    return _call("get_intake_queue")
