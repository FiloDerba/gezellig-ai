from datetime import date

import streamlit as st

from dutch_learning import data, shared

STATUSES = ["All", "Due", "New", "Learning", "Mature"]

today = date.today()
chapter_names = [row["chapter"] for row in data.chapters()]

with st.container(horizontal=True):
    chapter = st.selectbox("Chapter", ["All"] + chapter_names)
    search = st.text_input("Search", placeholder="Dutch or English")

status = st.segmented_control("Status", STATUSES, default="All", label_visibility="collapsed")

rows = data.words(
    chapter=None if chapter == "All" else chapter,
    search=search.strip() or None,
)

if status == "Due":
    rows = [word for word in rows if word.srs.due_date <= today]
elif status and status != "All":
    rows = [word for word in rows if word.srs.maturity == status.lower()]

st.caption(f"{len(rows)} word(s)")

if not rows:
    st.info("Nothing matches those filters.", icon=":material/search_off:")
    st.stop()

st.dataframe(
    [
        {
            "Dutch": word.dutch,
            "English": word.english,
            "Type": word.word_type,
            "Chapter": word.chapter,
            "Status": "Due" if word.srs.due_date <= today else word.srs.maturity.capitalize(),
            "Due in": shared.format_days(max((word.srs.due_date - today).days, 0)),
            "Reviews": word.srs.reps,
            "Ease": round(word.srs.ease_factor, 2),
            "Audio": data.audio_path(word) is not None,
        }
        for word in rows
    ],
    width="stretch",
    hide_index=True,
    column_config={"Audio": st.column_config.CheckboxColumn("Audio")},
)

with st.expander("Delete a word", icon=":material/delete:"):
    options = {f"{word.dutch} — {word.english}": word.id for word in rows}
    choice = st.selectbox("Word", list(options), label_visibility="collapsed")
    if st.button("Delete", type="primary", icon=":material/delete_forever:"):
        data.delete_word(options[choice])
        shared.reset_session()
        st.toast(f"Deleted {choice}", icon=":material/check:")
        st.rerun()
