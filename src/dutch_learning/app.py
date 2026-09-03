import os

import streamlit as st
from dotenv import load_dotenv

from dutch_learning import api
from dutch_learning.ai import make_hint_agent
from dutch_learning.views import browse, manage, vocabulary

load_dotenv()

st.set_page_config(page_title="Vocabulary", page_icon="🇳🇱", layout="centered")

PAGES = {"Vocabulary": vocabulary, "Word list": browse, "Manage": manage}


@st.cache_resource
def _get_agent():
    model = os.environ.get("DUTCH_MODEL", "google:gemini-3.6-flash")
    return make_hint_agent(model)


def _agent_or_error() -> tuple[object | None, str | None]:
    """Build the hint agent lazily; a missing key or bad model must not break studying."""
    try:
        return _get_agent(), None
    except Exception as exc:  # noqa: BLE001 - reported in the UI instead of crashing the page
        return None, str(exc)


def main() -> None:
    try:
        overview = api.overview()
    except api.ApiError as exc:
        st.title("Vocabulary 🇳🇱")
        st.error(str(exc))
        st.write("Start the backend, then reload this page:")
        st.code("cd django && uv run --project .. python manage.py runserver")
        return

    if overview["total_words"] == 0:
        st.title("Vocabulary 🇳🇱")
        st.info(
            "No words yet. Load the sample deck below to start studying in a few seconds, "
            "or import an Anki `.apkg` export."
        )
        manage.render()
        return

    page = st.sidebar.radio("Page", list(PAGES), label_visibility="collapsed")

    if page == "Vocabulary":
        vocabulary.render(_agent_or_error())
    else:
        PAGES[page].render()


main()
