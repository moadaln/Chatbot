# APP / Agent

This folder contains the user-facing application:
- **Streamlit UI**: `frontend.py`
- **Agent runtime**: `agent_runtime.py`

The UI sends user questions to the agent runtime. The agent uses an LLM (OpenAI API) and when needed calls the Neo4j tools exposed by the MCP server in `APP/Server`.

## Run (local)

From the repository root (after installing `requirements.txt` and creating your `.env`):

```bash
cd APP/Agent
streamlit run frontend.py
```

## Configuration

The Agent/UI reads these environment variables (typically from the root `.env`):

- `OPENAI_API_KEY` – OpenAI API key (required)
- `MCP_SERVER_URL` – MCP endpoint URL (default: `http://localhost:8000/mcp`)
- `OPENAI_MODEL` – model name (default: `gpt-5.1`)

You can also change `MCP_SERVER_URL` and `OPENAI_MODEL` directly in the Streamlit sidebar at runtime.

## What happens when you chat

- The Streamlit app maintains a local `SQLiteSession` for conversation state.
- Each user message triggers one agent turn (`run_agent_turn(...)`).
- If enabled in the sidebar, the UI shows tool-call steps and raw tool outputs for debugging.
