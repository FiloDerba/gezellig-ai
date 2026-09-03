from datetime import date

import streamlit as st

from dutch_learning.db import get_stats


def render(conn) -> None:
    st.title("Stats")
    stats = get_stats(conn, date.today())

    col1, col2, col3 = st.columns(3)
    col1.metric("Due today", stats["due_today"])
    col2.metric("Total words", stats["total_words"])
    col3.metric("Total reviews", stats["total_reviews"])

    st.write("---")
    st.subheader("By chapter")

    if not stats["by_chapter"]:
        st.info("No data yet.")
        return

    chapter_data = [
        {"Chapter": r["chapter"], "Words": r["count"], "Reviews": r["reviews"]}
        for r in stats["by_chapter"]
    ]
    st.dataframe(chapter_data, use_container_width=True)
