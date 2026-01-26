# neo4j_tools_core.py
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver

# ============================================================
# ENV / Neo4j (shared)
# ============================================================
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "movies")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "movies")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")  # optional

_driver: Driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
)


def get_session():
    """Return a Neo4j session (respects NEO4J_DATABASE if provided)."""
    if NEO4J_DATABASE:
        return _driver.session(database=NEO4J_DATABASE)
    return _driver.session()


# ------------------------------------------------------------
# JSON-safe conversion (Neo4j temporal etc.)
# ------------------------------------------------------------
def to_json(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (list, tuple)):
        return [to_json(x) for x in v]
    if isinstance(v, dict):
        return {k: to_json(val) for k, val in v.items()}

    # neo4j.time.* often provides iso_format()
    if hasattr(v, "iso_format") and callable(getattr(v, "iso_format")):
        try:
            return v.iso_format()
        except Exception:
            pass

    # python datetime/date/time
    if hasattr(v, "isoformat") and callable(getattr(v, "isoformat")):
        try:
            return v.isoformat()
        except Exception:
            pass

    # Neo4j Record / Node etc.
    try:
        return to_json(dict(v))
    except Exception:
        return str(v)


def records_to_list(result, limit: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for i, record in enumerate(result):
        if i >= limit:
            break
        rows.append(to_json(record.data()))
    return rows


# ============================================================
# Core functionality (shared by MCP + LangChain)
# ============================================================

def get_schema_core() -> Dict[str, Any]:
    """Static schema description (no Neo4j call)."""
    return {
        "nodes": {
            "Stop": ["stop_id", "lau", "geometry_wkt"],
            "Route": [
                "route_id", "line", "lau",
                "trip_sample_count",
                "total_trip_travel_time_seconds",
                "mean_trip_travel_time_seconds",
            ],
            "Trip": [
                "trip_id", "date", "line", "route_id", "lau",
                "from_time", "to_time", "travel_time_seconds",
            ],
            "TravelSegment": ["segment_id", "from_stop_id", "to_stop_id", "lau"],
        },
        "relationships": {
            "HAS_TRIP": "(:Route)-[:HAS_TRIP]->(:Trip)",
            "FROM_STOP": "(:TravelSegment)-[:FROM_STOP]->(:Stop)",
            "TO_STOP": "(:TravelSegment)-[:TO_STOP]->(:Stop)",
            "TRAVELS_ON": "(:Trip)-[:TRAVELS_ON]->(:TravelSegment) [event]",
            "DWELL_AT": "(:Trip)-[:DWELL_AT]->(:Stop) [event]",
            "SERVES": "(:Route)-[:SERVES]->(:Stop) [aggregate dwell]",
            "HAS_SEGMENT": "(:Route)-[:HAS_SEGMENT]->(:TravelSegment) [aggregate travel]",
        },
        "notes": [
            "TravelSegment ist global: segment_id = 'from_stop_id|to_stop_id'.",
            "Trip ist eindeutig über (trip_id, date).",
            "Events: DWELL_AT(dwell_time_seconds), TRAVELS_ON(travel_time_seconds).",
            "Aggregates: SERVES(mean_dwell_time_seconds), HAS_SEGMENT(segment_mean_travel_time_seconds).",
        ],
    }


def run_query_core(
    cypher: str,
    parameters: Optional[Dict[str, Any]] = None,
    limit: int = 100,
    enforce_limit: bool = True,
) -> List[Dict[str, Any]]:
    """Execute a Cypher query and return JSON-safe rows."""
    params = parameters or {}

    if enforce_limit:
        if re.search(r"(?i)\blimit\b", cypher) is None:
            safe_limit = max(1, min(int(limit), 1000))
            cypher = cypher.rstrip() + f"\nLIMIT {safe_limit}"

    with get_session() as session:
        result = session.run(cypher, params)
        return records_to_list(result, int(limit))


def close_driver() -> None:
    """Close the shared Neo4j driver (optional)."""
    try:
        _driver.close()
    except Exception:
        pass
