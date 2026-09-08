"""Entry point: `uv run streamlit run streamlit_app.py`.

There is no backend process. `dutch_learning.data` configures Django in this process and
talks to the database in `django/.env` directly.
"""

import os
import sys
from pathlib import Path

# When running from the cloned repo without package install (Streamlit Cloud, local dev):
# add src/ so `from dutch_learning import ...` resolves to the source tree.
# Must happen before any dutch_learning imports so django_bootstrap path calc is correct.
_REPO_ROOT = Path(__file__).parent
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

import streamlit as st  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

# Streamlit Cloud stores secrets as TOML; bridge them into os.environ so Django settings
# and AI provider clients pick them up via standard env-var reads.
# Must run before `dutch_learning.data` triggers django.setup().
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except Exception:
    pass  # No secrets configured (local dev with .env files)

from dutch_learning import data  # noqa: E402

load_dotenv()  # local dev fallback; env vars set above already win

st.set_page_config(
    page_title="Dutch",
    page_icon=":material/translate:",
    layout="centered",
)

PAGE_DIR = str(_REPO_ROOT / "src/dutch_learning/app_pages")

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
