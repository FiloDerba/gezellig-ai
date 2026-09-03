import streamlit as st

from dutch_learning.db import get_all_words, get_chapters


def render(conn) -> None:
    st.title("Browse")

    chapters = ["All"] + get_chapters(conn)
    chapter_filter = st.selectbox("Chapter", chapters)
    search = st.text_input("Search (Dutch or English)")

    chapter = None if chapter_filter == "All" else chapter_filter
    search_str = search.strip() or None

    rows = get_all_words(conn, chapter=chapter, search=search_str)

    st.caption(f"{len(rows)} word(s)")

    if not rows:
        st.info("No words match the filter.")
        return

    table_data = [
        {
            "Dutch": w.dutch,
            "English": w.english,
            "Type": w.word_type,
            "Chapter": w.chapter,
            "Due": s.due_date.isoformat(),
            "Reviews": s.reps,
        }
        for w, s in rows
    ]
    st.dataframe(table_data, use_container_width=True)
