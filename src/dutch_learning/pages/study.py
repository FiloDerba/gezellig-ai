from datetime import date
from pathlib import Path

import streamlit as st

from dutch_learning import ai as ai_mod
from dutch_learning.db import get_due_cards, update_srs_state
from dutch_learning.srs import update_sm2

MEDIA_DIR = Path("data/media")
RATINGS = {"Again": 0, "Hard": 1, "Good": 3, "Easy": 5}


def _load_due(conn):
    """Load due cards into session_state if not already loaded."""
    if "due_cards" not in st.session_state:
        st.session_state.due_cards = get_due_cards(conn, date.today())
        st.session_state.card_idx = 0
        st.session_state.flipped = False


def _current_card(conn):
    _load_due(conn)
    cards = st.session_state.due_cards
    idx = st.session_state.card_idx
    if idx >= len(cards):
        return None, None
    return cards[idx]


def _advance(conn):
    st.session_state.card_idx += 1
    st.session_state.flipped = False
    # Reload if we've gone through all cards
    if st.session_state.card_idx >= len(st.session_state.due_cards):
        del st.session_state["due_cards"]


def render(conn, agent) -> None:
    st.title("Study")
    _load_due(conn)
    total_due = len(st.session_state.due_cards)
    remaining = total_due - st.session_state.card_idx

    if remaining <= 0:
        st.success(f"All {total_due} cards done for today!")
        if st.button("Reset session"):
            del st.session_state["due_cards"]
            st.rerun()
        return

    st.caption(f"{remaining} card(s) remaining today")

    word, srs = _current_card(conn)

    st.markdown(f"## {word.dutch}")
    st.caption(f"{word.word_type} · {word.chapter}")

    audio_path = MEDIA_DIR / word.audio_file if word.audio_file else None
    if audio_path and audio_path.exists():
        st.audio(str(audio_path))

    if not st.session_state.flipped:
        if st.button("Show answer"):
            st.session_state.flipped = True
            st.rerun()
        return

    st.markdown(f"**{word.english}**")

    with st.expander("Ask AI for a hint"):
        question = st.text_input("Your question", key=f"hint_q_{st.session_state.card_idx}")
        if question:
            with st.spinner("Thinking..."):
                hint = ai_mod.get_hint(agent, word.dutch, word.word_type, word.english, question)
            st.markdown(hint)

    st.write("---")
    cols = st.columns(4)
    for col, (label, quality) in zip(cols, RATINGS.items()):
        if col.button(label, use_container_width=True):
            new_state = update_sm2(srs, quality)
            update_srs_state(conn, new_state)
            _advance(conn)
            st.rerun()
