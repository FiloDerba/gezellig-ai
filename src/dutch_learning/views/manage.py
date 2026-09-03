import streamlit as st

from dutch_learning import api, ui

WORD_TYPES = ["noun", "verb", "adjective", "adverb", "phrase", "other"]


def _reset_study_session() -> None:
    """Drop the cached queue so newly added words show up immediately."""
    stale = ("queue", "due_total", "card_idx", "flipped", "session_size", "hint_")
    for key in list(st.session_state.keys()):
        if str(key).startswith(stale):
            del st.session_state[key]


def render() -> None:
    ui.inject_css()
    overview = api.overview()
    ui.header("Manage", f"{overview['total_words']} word(s) in the database")

    st.subheader("Start with the sample deck")
    st.write(
        "Adds a handful of common Dutch words across a few chapters, "
        "so you can try studying right away."
    )
    if st.button("Load sample words"):
        added = api.load_sample_deck()
        _reset_study_session()
        if added:
            st.success(f"Added {added} word(s).")
        else:
            st.info("Sample words are already in the database.")
        st.rerun()

    st.divider()

    st.subheader("Import an Anki deck")
    st.write("Anki decks are imported from the terminal, straight into the backend:")
    st.code("cd django && uv run --project .. python manage.py import_anki /path/to/deck.apkg")

    st.divider()

    st.subheader("Add a word yourself")
    chapter_names = [row["chapter"] for row in api.chapters()]
    with st.form("add_word", clear_on_submit=True):
        dutch = st.text_input("Dutch")
        english = st.text_input("English")
        col1, col2 = st.columns(2)
        word_type = col1.selectbox("Type", WORD_TYPES)
        chapter = col2.text_input(
            "Chapter", value=chapter_names[0] if chapter_names else "Custom"
        )
        submitted = st.form_submit_button("Add word")

    if submitted:
        if not dutch.strip() or not english.strip():
            st.warning("Both Dutch and English are required.")
        else:
            api.add_word(dutch.strip(), english.strip(), word_type, chapter.strip() or "Custom")
            _reset_study_session()
            st.success(f"Added “{dutch.strip()}”. It is due today.")
