"""Entry point: `uv run streamlit run streamlit_app.py`.

There is no backend process. `dutch_learning.data` configures Django in this process and
talks to the database in `django/.env` directly.
"""

import streamlit as st
from dotenv import load_dotenv

from dutch_learning import data

load_dotenv()

st.set_page_config(
    page_title="Dutch",
    page_icon=":material/translate:",
    layout="centered",
)

PAGE_DIR = "src/dutch_learning/app_pages"

# Connections can go stale between reruns, and Streamlit has no request cycle to reset them.
data.begin_run()

try:
    st.session_state.overview = data.overview()
except data.DataError as exc:
    st.title("Dutch", icon=":material/translate:")
    st.error(str(exc), icon=":material/error:")
    st.caption("Check `DATABASE_URL` in `django/.env`, then reload this page.")
    st.stop()

if st.session_state.overview.total_words == 0:
    pages = [st.Page(f"{PAGE_DIR}/manage.py", title="Manage", icon=":material/settings:")]
else:
    pages = [
        st.Page(f"{PAGE_DIR}/study.py", title="Study", icon=":material/style:", default=True),
        st.Page(f"{PAGE_DIR}/speaking.py", title="Speaking", icon=":material/mic:"),
        st.Page(f"{PAGE_DIR}/assistant.py", title="Assistant", icon=":material/forum:"),
        st.Page(f"{PAGE_DIR}/progress.py", title="Progress", icon=":material/insights:"),
        st.Page(f"{PAGE_DIR}/words.py", title="Words", icon=":material/list:"),
        st.Page(f"{PAGE_DIR}/manage.py", title="Manage", icon=":material/settings:"),
    ]

page = st.navigation(pages, position="top")
page.run()
