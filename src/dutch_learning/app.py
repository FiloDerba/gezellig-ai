import os

import streamlit as st
from dotenv import load_dotenv

from dutch_learning.ai import make_hint_agent
from dutch_learning.db import get_conn, init_db
from dutch_learning.pages import browse, stats, study

load_dotenv()

st.set_page_config(page_title="Dutch Learning", page_icon="🇳🇱", layout="centered")


@st.cache_resource
def _get_conn():
    conn = get_conn()
    init_db(conn)
    return conn


@st.cache_resource
def _get_agent():
    model = os.getenv("DUTCH_MODEL", "google:gemini-3.6-flash")
    return make_hint_agent(model)


def main():
    conn = _get_conn()
    agent = _get_agent()

    page = st.sidebar.radio("Navigate", ["Study", "Browse", "Stats"])

    if page == "Study":
        study.render(conn, agent)
    elif page == "Browse":
        browse.render(conn)
    elif page == "Stats":
        stats.render(conn)


main()
