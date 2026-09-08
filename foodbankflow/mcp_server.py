"""Demo MCP server for FoodBankFlow's data sources.

Stands in for the real backends this would call in production - a
warehouse/inventory table, a client-registration system, and the vision
step that reads each donation drop-off photo (see README). Serves the same
seed data as before (via core.py's load_* readers, unchanged) over MCP
instead of the agent reading local JSON files directly, so a real backend
can later replace this process without touching agent/tool code - see
data_client.py, which is the only thing that needs to change (point
MCP_DATA_SERVER_URL at a streamable-HTTP server instead of spawning this
one over stdio).

Run standalone for manual testing:
    python -m foodbankflow.mcp_server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import core

mcp = FastMCP("foodbankflow-data")


@mcp.tool()
def get_inventory() -> list[dict]:
    """Current stock on hand: item, category, units, perishable, expiry."""
    return core.load_inventory()


@mcp.tool()
def get_families() -> dict:
    """Registered families (household size, pickup day, dietary constraints) and the allocation policy."""
    return core.load_families()


@mcp.tool()
def get_intake_queue() -> list[dict]:
    """Pending donations from the photo/vision drop-off step: donor + line items."""
    return core.load_intake()


if __name__ == "__main__":
    mcp.run(transport="stdio")
