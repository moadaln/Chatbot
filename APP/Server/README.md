# APP / Server (MCP)

This folder provides an MCP server that exposes a small set of Neo4j tools to the agent.

## Files

- `server.py` – MCP server (tool registration + HTTP transport)
- `neo4j_tools_core.py` – core Neo4j logic (Cypher execution + JSON-safe conversion)

## Exposed tools

- `get_schema` – returns a static schema description (no Neo4j call)
- `run_query` – executes a Cypher query in Neo4j and returns JSON-safe rows

## Run (local)

From the repository root (after installing `requirements.txt` and creating your `.env`):

```bash
cd APP/Server
python server.py
```

The server runs with a *streamable HTTP* transport. In the agent/UI, the MCP endpoint is commonly configured as:

- `http://localhost:8000/mcp`

(Exact host/port/path depend on your MCP runtime defaults.)

## Configuration

The server reads Neo4j connection settings from environment variables (typically from the root `.env`):

- `NEO4J_URI` (example: `neo4j://localhost:7687`)
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `NEO4J_DATABASE` (optional)

## Notes

- Neo4j must be running before calling `run_query`.
- `server.py` is a thin wrapper and delegates database work to `neo4j_tools_core.py`.
