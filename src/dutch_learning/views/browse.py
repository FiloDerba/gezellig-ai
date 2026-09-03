from datetime import date

import streamlit as st

from dutch_learning import api, ui

STATUS_FILTERS = ["All", "Due", "New", "Learning", "Mature"]


def render() -> None:
    ui.inject_css()
    ui.header("Word list", "Filter and search everything in your deck")
    today = date.today()

    col1, col2 = st.columns(2)
    chapter_names = [row["chapter"] for row in api.chapters()]
    chapter_filter = col1.selectbox("Chapter", ["All"] + chapter_names)
    status_filter = col2.selectbox("Status", STATUS_FILTERS)
    search = st.text_input("Search (Dutch or English)")

    rows = api.words(
        chapter=None if chapter_filter == "All" else chapter_filter,
        search=search.strip() or None,
    )

    if status_filter == "Due":
        rows = [w for w in rows if api.parse_date(w["srs"]["due_date"]) <= today]
    elif status_filter != "All":
        rows = [w for w in rows if w["srs"]["maturity"] == status_filter.lower()]

    st.caption(f"{len(rows)} word(s)")

    if not rows:
        st.info("No words match the filter. Try clearing the search or picking another chapter.")
        return

    table_data = []
    for word in rows:
        srs = word["srs"]
        due = api.parse_date(srs["due_date"])
        table_data.append({
            "Dutch": word["dutch"],
            "English": word["english"],
            "Type": word["word_type"],
            "Chapter": word["chapter"],
            "Status": "Due" if due <= today else srs["maturity"].capitalize(),
            "Due in (days)": (due - today).days,
            "Due": srs["due_date"],
            "Reviews": srs["reps"],
            "Ease": round(srs["ease_factor"], 2),
        })
    st.dataframe(table_data, width="stretch", hide_index=True)

    with st.expander("Delete a word"):
        options = {f"{w['dutch']} — {w['english']}": w["id"] for w in rows}
        choice = st.selectbox("Word", list(options))
        if st.button("Delete", type="primary"):
            api.delete_word(options[choice])
            st.session_state.pop("queue", None)
            st.success(f"Deleted “{choice}”.")
            st.rerun()
