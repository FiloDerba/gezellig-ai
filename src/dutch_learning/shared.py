"""Helpers shared by the pages: cached agents, session handling and small formatters."""

import os

import streamlit as st

from ai_playground.agent import Agent as PlaygroundAgent
from dutch_learning import ai, data, vocab_tools

DAILY_GOALS = [10, 20, 30, 50, 100]
DEFAULT_GOAL = 20

#: Rating label -> the colour Streamlit markdown gives its button.
RATING_COLOURS = {"Again": "red", "Hard": "orange", "Good": "green", "Easy": "blue"}

SESSION_KEYS = ("cards", "due_total", "card_idx", "flipped", "session_size")


def _model() -> str:
    return os.environ.get("DUTCH_MODEL", ai.DEFAULT_MODEL)


@st.cache_resource
def _agents(model: str) -> dict:
    return {
        "hint": ai.make_agent(model),
        "coach": ai.make_coach(model),
        "pronunciation": ai.make_pronunciation_coach(model),
    }


def agent(kind: str):
    """A tutor agent, or None with a reason when the model or API key is unusable."""
    try:
        return _agents(_model())[kind], None
    except Exception as exc:  # noqa: BLE001 - shown in the UI rather than breaking the page
        return None, str(exc)


@st.cache_resource
def _research_agent(model: str) -> PlaygroundAgent:
    """Shared across sessions, which is safe because the page never uses its own history.

    Cached on the model alone: the deck is read through tools at call time, so the agent
    never holds a stale copy of it.
    """
    return PlaygroundAgent(model, extra_context=vocab_tools.CONTEXT, extra_tools=vocab_tools.TOOLS)


def research_agent():
    """The ai-playground agent, with web search plus the learner's own vocabulary."""
    try:
        return _research_agent(os.environ.get("PLAYGROUND_MODEL", "gemini-3.6-flash")), None
    except Exception as exc:  # noqa: BLE001 - shown in the UI rather than breaking the page
        return None, str(exc)


def format_days(days: int) -> str:
    if days == 1:
        return "1 day"
    if days < 30:
        return f"{days} days"
    if days < 365:
        return f"{round(days / 30)} mo"
    return f"{days / 365:.1f} yr"


def daily_goal() -> int:
    return st.session_state.get("daily_goal", DEFAULT_GOAL)


def load_session() -> None:
    """Build today's queue once; later reruns reuse it so the order stays stable."""
    if "cards" in st.session_state:
        return
    queue = data.study_queue(limit=daily_goal())
    st.session_state.cards = queue.cards
    st.session_state.due_total = queue.due_total
    st.session_state.card_idx = 0
    st.session_state.flipped = False
    st.session_state.session_size = len(queue.cards)


def reset_session() -> None:
    for key in SESSION_KEYS:
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if str(key).startswith(("insight_", "answer_", "question_", "attempt_")):
            del st.session_state[key]


def skip_current() -> None:
    cards = st.session_state.cards
    cards.append(cards.pop(st.session_state.card_idx))
    st.session_state.flipped = False
