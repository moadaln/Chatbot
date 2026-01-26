# server.py (refactored to use shared core library)
from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from neo4j_tools_core_nocharts import (
    get_schema_core,
    run_query_core,
)

mcp = FastMCP(
    "neo4j-mcp-server",
    stateless_http=True,
    json_response=True,
)

@mcp.tool()
def get_schema() -> Dict[str, Any]:
    """Statische Schema-Beschreibung (kein Neo4j-Call)."""
    return get_schema_core()

@mcp.tool()
def run_query(
    cypher: str,
    parameters: Optional[Dict[str, Any]] = None,
    limit: int = 100,
    enforce_limit: bool = True,
) -> List[Dict[str, Any]]:
    """Führt eine Cypher-Query in Neo4j aus und gibt JSON-safe rows zurück."""
    return run_query_core(cypher=cypher, parameters=parameters, limit=limit, enforce_limit=enforce_limit)

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
