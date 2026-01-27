# agent_runtime.py
import os
from typing import Any, Dict, List, Optional, Tuple

from agents import Agent, Runner, SQLiteSession, RunConfig
from agents.mcp import MCPServerStreamableHttp
from agents.model_settings import ModelSettings

DEFAULT_INSTRUCTIONS = """
Du bist ein Assistent für ÖPNV-Zeitreihen in Neo4j (Non-technical Nutzer).

Grundprinzip:
- bilde selber queries und nutze mcp tool um die auszuführen
- wenn die frage komplex ist kannst du sie in schritte teilen und führe mehere queries aus bis du auf die Antwort kommst
- nutze get-schema um das schema zu erkennen
- bei jeder Frage schaue mal das schema nach bevor du Query bildest
- Verwende MCP-Tools, wann immer du Fakten/Zahlen brauchst.
- Antworte kurz und verständlich. Keine Cypher im Output, außer der User fragt explizit.
- für daten nutze folgende Format: YYYY-MM-DD als String deswegen bitte bei der suche Datum in echtes Date umwandeln
  Beispiel: WHERE date(t.date) >= date('2022-01-01') AND date(t.date) <= date('2022-01-31')
- Liste kurz die verwendeten Tools + Parameter (ohne interne Fehlerdetails, außer es ist relevant).

WICHTIG:
- Keine Visualisierung/Charts erzeugen. Antworte rein textbasiert.
- Wenn der User nach “Graph/Diagramm/Plot/Chart/Trend/Verlauf” fragt: erkläre die Ergebnisse in Worten (und ggf. mit Zahlen),
  aber rufe KEINE Chart-Tools auf.

"""


def _tool_name_from_raw(raw: Any) -> str:
    if isinstance(raw, dict):
        return (
            raw.get("name")
            or raw.get("tool_name")
            or (raw.get("function") or {}).get("name")
            or "unknown_tool"
        )
    # pydantic / objects
    if hasattr(raw, "name"):
        return getattr(raw, "name")
    if hasattr(raw, "function") and hasattr(raw.function, "name"):
        return raw.function.name
    return "unknown_tool"

def _tool_args_from_raw(raw: Any) -> Any:
    if isinstance(raw, dict):
        return raw.get("arguments") or (raw.get("function") or {}).get("arguments")
    if hasattr(raw, "arguments"):
        return getattr(raw, "arguments")
    if hasattr(raw, "function") and hasattr(raw.function, "arguments"):
        return raw.function.arguments
    return None

async def run_agent_turn(
    user_text: str,
    session: SQLiteSession,
    mcp_url: str,
    model: str = "gpt-5.1",
    instructions: str = DEFAULT_INSTRUCTIONS,
    timeout_seconds: int = 60,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Returns:
      - final assistant text
      - trace list: [{"type": "...", "name": "...", "args": ..., "output": ...}, ...]
    """
    trace: List[Dict[str, Any]] = []

    async with MCPServerStreamableHttp(
        name="Neo4j MCP",
        params={
            "url": mcp_url,
            "timeout": timeout_seconds,
        },
        cache_tools_list=True,
        max_retry_attempts=3,
        use_structured_content=True,
    ) as server:
        agent = Agent(
            name="Transit Analyst",
            instructions=instructions,
            mcp_servers=[server],
            model=model,
            model_settings=ModelSettings(tool_choice="auto"),
        )

        result = await Runner.run(
            agent,
            user_text,
            session=session,
            run_config=RunConfig(tracing_disabled=True),
        )

        # Trace aus new_items bauen (Tool calls/outputs/messages)
        last_tool_name: Optional[str] = None
        for item in result.new_items:
            t = getattr(item, "type", None)

            if t == "tool_call_item":
                raw = getattr(item, "raw_item", None)
                last_tool_name = _tool_name_from_raw(raw)
                trace.append({
                    "type": "tool_call",
                    "name": last_tool_name,
                    "args": _tool_args_from_raw(raw),
                })

            elif t == "tool_call_output_item":
                out = getattr(item, "output", None)
                trace.append({
                    "type": "tool_output",
                    "tool_name": last_tool_name,
                    "output": out,
                })

            elif t == "message_output_item":
                # Optional fürs Debugging
                trace.append({
                    "type": "message",
                    "output": str(getattr(item, "raw_item", ""))[:5000],
                })

    return str(result.final_output), trace
