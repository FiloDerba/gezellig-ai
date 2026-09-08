import streamlit as st

from dutch_learning import data, shared

WORD_TYPES = ["noun", "verb", "adjective", "adverb", "phrase", "other"]

overview = st.session_state.overview
st.caption(f"{overview.total_words} word(s) in the database")

if overview.total_words == 0:
    st.info(
        "The deck is empty. Load the sample words to try it out, or import an Anki export.",
        icon=":material/inbox:",
    )

st.subheader("Sample deck", icon=":material/playlist_add:")
st.write("Thirty common Dutch words across a few chapters, enough to try a session.")
if st.button("Load sample words", icon=":material/download:"):
    added = data.load_sample_deck()
    shared.reset_session()
    st.toast(f"Added {added} word(s)." if added else "Already loaded.", icon=":material/check:")
    st.rerun()

st.subheader("Import an Anki deck", icon=":material/upload_file:")
st.write("Decks are imported from the terminal, straight into the database:")
st.code("cd django && uv run --project .. python manage.py import_anki /path/to/deck.apkg")
st.caption("Audio from the deck lands in `data/media`, which powers the Speaking page.")

st.subheader("Add a word", icon=":material/add_circle:")
chapter_names = [row["chapter"] for row in data.chapters()]
with st.form("add_word", clear_on_submit=True):
    dutch = st.text_input("Dutch")
    english = st.text_input("English")
    with st.container(horizontal=True):
        word_type = st.selectbox("Type", WORD_TYPES)
        chapter = st.text_input("Chapter", value=chapter_names[0] if chapter_names else "Custom")
    submitted = st.form_submit_button("Add word", icon=":material/add:")

if submitted:
    if not dutch.strip() or not english.strip():
        st.warning("Both Dutch and English are required.", icon=":material/warning:")
    else:
        data.add_word(dutch.strip(), english.strip(), word_type, chapter.strip() or "Custom")
        shared.reset_session()
        st.toast(f"Added {dutch.strip()}, due today.", icon=":material/check:")
