import os
import json
import uuid
import asyncio
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from agents import SQLiteSession
from agent_runtime import run_agent_turn

st.set_page_config(page_title="Neo4j MCP Chatbot", layout="wide")


# ----------------------------
# async helper
# ----------------------------
def run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


# ----------------------------
# unwrap tool outputs (JSON strings + {type:"text", text:"..."} + {"result": ...})
# ----------------------------
def _try_parse_json(x: Any) -> Any:
    if not isinstance(x, str):
        return x
    s = x.strip()
    if not s or s[0] not in "{[":
        return x
    try:
        return json.loads(s)
    except Exception:
        return x


def _unwrap(x: Any) -> Any:
    x = _try_parse_json(x)

    # wrapper from some SDKs: {"type":"text","text":"{...json...}"}
    if isinstance(x, dict) and x.get("type") == "text" and "text" in x:
        return _unwrap(x["text"])

    # MCP-style wrapper: {"result": ...}
    if isinstance(x, dict) and "result" in x and len(x) == 1:
        return _unwrap(x["result"])

    return x


def _extract_rows(x: Any) -> List[Dict[str, Any]]:
    x = _unwrap(x)

    if isinstance(x, list) and x and isinstance(x[0], dict):
        return x

    if isinstance(x, dict):
        for k in ("rows", "data", "result"):
            v = x.get(k)
            v = _unwrap(v)
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v

    return []


    # if isinstance(x, dict) and x.get("schema") == "vega-lite":
    #     data = x.get("data")
    #     spec = x.get("spec")
    #     if isinstance(data, list) and isinstance(spec, dict):
    #         return x

    # return None


# ----------------------------
# UI
# ----------------------------
st.sidebar.header("Settings")
mcp_url = st.sidebar.text_input("MCP Server URL", value=os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp"))
model = st.sidebar.text_input("Model", value=os.getenv("OPENAI_MODEL", "gpt-5.1"))
show_steps = st.sidebar.checkbox("Show tool steps", value=True)
show_raw = st.sidebar.checkbox("Show raw tool outputs", value=True)

st.title("Neo4j MCP Chatbot")

if "session_id" not in st.session_state:
    st.session_state.session_id = f"ui_{uuid.uuid4().hex}"
if "agent_session" not in st.session_state:
    st.session_state.agent_session = SQLiteSession(st.session_state.session_id)
if "messages" not in st.session_state:
    st.session_state.messages = []

# render history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_text = st.chat_input("Frage… (z.B. langsamstes Segment 01.01–07.01.2022)")

if user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        with st.spinner("Agent läuft…"):
            final_text, trace = run_async(
                run_agent_turn(
                    user_text=user_text,
                    session=st.session_state.agent_session,
                    mcp_url=mcp_url,
                    model=model,
                )
            )

        st.markdown(final_text)
        st.session_state.messages.append({"role": "assistant", "content": final_text})

        # Steps (debug)
        if show_steps:
            with st.expander("Tool steps"):
                for item in trace:
                    if item.get("type") == "tool_call":
                        st.write(f"Tool call: {item.get('name')}")
                        if item.get("args") is not None:
                            st.code(str(item["args"]))
                    # elif item.get("type") == "tool_output":
                    #     st.write(f"Tool output: {item.get('tool_name', 'unknown_tool')}")

        # Raw outputs (helpful while debugging)
        if show_raw:
            with st.expander("Raw tool outputs"):
                for item in trace:
                    if item.get("type") != "tool_output":
                        continue
                    tool = item.get("tool_name", "unknown_tool")
                    out = _unwrap(item.get("output"))
                    st.markdown(f"**{tool}**")
                    # If rows -> show table; else show JSON
                    rows = _extract_rows(out)
                    if rows:
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    # else:
                    #     st.code(json.dumps(out, ensure_ascii=False, indent=2))
