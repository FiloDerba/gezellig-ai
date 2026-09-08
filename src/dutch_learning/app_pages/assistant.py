import time

import streamlit as st
from pydantic_ai.messages import ToolCallPart

from dutch_learning import data, shared

SUGGESTIONS = {
    ":blue[:material/quiz:] Quiz me": "Quiz me on the words I have studied so far",
    ":green[:material/edit_note:] Make sentences": (
        "Write three Dutch sentences using only words I already know, with translations"
    ),
    ":orange[:material/trending_up:] What next": "Based on what I know, what should I study next?",
    ":violet[:material/newspaper:] Dutch news": "What is in the Dutch news today?",
}

agent, agent_error = shared.research_agent()

if agent is None:
    st.error(f"Assistant unavailable: {agent_error}", icon=":material/error:")
    st.stop()

st.caption(
    f"Can search the {len(data.encountered())} word(s) you have studied, plus the web. "
    "Ask it to quiz you or build sentences from what you know."
)

st.session_state.setdefault("assistant_turns", [])  # what gets rendered
st.session_state.setdefault("assistant_history", [])  # what the model is given as context

if st.session_state.assistant_turns and st.button("Clear chat", icon=":material/delete_sweep:"):
    st.session_state.assistant_turns = []
    st.session_state.assistant_history = []
    st.rerun()

for turn in st.session_state.assistant_turns:
    with st.chat_message(turn["role"]):
        if turn.get("tools"):
            with st.expander(f"Used {', '.join(turn['tools'])}", type="compact"):
                for call in turn["tools"]:
                    st.caption(call)
        st.markdown(turn["content"])

prompt = st.chat_input("Ask anything", submit_mode="disable")

if not prompt and not st.session_state.assistant_turns:
    picked = st.pills("Try asking", list(SUGGESTIONS), label_visibility="collapsed")
    if picked:
        prompt = SUGGESTIONS[picked]

if not prompt:
    st.stop()

st.session_state.assistant_turns.append({"role": "user", "content": prompt})
with st.chat_message("user"):
    st.markdown(prompt)

with st.chat_message("assistant"):
    started = time.monotonic()
    with st.status(":shimmer[Thinking]", type="compact") as status:
        try:
            reply, new_messages = agent.run(prompt, st.session_state.assistant_history)
        except Exception as exc:  # noqa: BLE001 - a failed turn must not clear the conversation
            status.update(label="Failed", state="error")
            st.error(f"The assistant could not answer: {exc}", icon=":material/error:")
            st.session_state.assistant_turns.pop()
            st.stop()

        tools = [
            part.tool_name
            for message in new_messages
            for part in getattr(message, "parts", [])
            if isinstance(part, ToolCallPart)
        ]
        for name in tools:
            with st.status(f"Called {name}", type="step", state="complete"):
                st.caption("Tool call")

        elapsed = time.monotonic() - started
        status.update(label=f"Thought for {elapsed:.0f}s", state="complete")

    st.markdown(reply)

st.session_state.assistant_history.extend(new_messages)
st.session_state.assistant_turns.append(
    {"role": "assistant", "content": reply, "tools": tools}
)
