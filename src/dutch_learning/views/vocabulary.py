from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from dutch_learning import ai as ai_mod
from dutch_learning import api, ui

MEDIA_DIR = Path("data/media")
RATINGS = {"Again": 0, "Hard": 1, "Good": 3, "Easy": 5}
PREVIEW_KEYS = {"Again": "again", "Hard": "hard", "Good": "good", "Easy": "easy"}
DAILY_GOAL_OPTIONS = [10, 20, 30, 50, 100]
DEFAULT_DAILY_GOAL = 20
QUICK_QUESTIONS = {
    "Mnemonic": "Give me a memorable mnemonic for this word.",
    "Example": "Give one example sentence in Dutch with an English translation.",
    "Etymology": "Where does this word come from?",
    "Pitfalls": "What do English speakers usually get wrong about this word?",
}


def _daily_goal() -> int:
    return st.session_state.get("daily_goal", DEFAULT_DAILY_GOAL)


def _load_session() -> None:
    """Fetch today's queue from the API unless a session is already in progress."""
    if "queue" not in st.session_state:
        payload = api.study_queue(limit=_daily_goal())
        st.session_state.queue = payload["results"]
        st.session_state.due_total = payload["due_total"]
        st.session_state.card_idx = 0
        st.session_state.flipped = False
        st.session_state.session_size = len(payload["results"])


def _reset_session() -> None:
    for key in ("queue", "due_total", "card_idx", "flipped", "session_size"):
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if str(key).startswith(("hint_cache_", "hint_q_", "hint_preset_")):
            del st.session_state[key]


def _skip_current() -> None:
    queue = st.session_state.queue
    queue.append(queue.pop(st.session_state.card_idx))
    st.session_state.flipped = False


def _format_days(days: int) -> str:
    if days == 1:
        return "1 day"
    if days < 30:
        return f"{days} days"
    if days < 365:
        return f"{round(days / 30)} mo"
    return f"{days / 365:.1f} yr"


def _snapshot(overview: dict) -> None:
    session_size = st.session_state.get("session_size", 0)
    done = min(st.session_state.get("card_idx", 0), session_size)
    total = overview["total_words"]
    mature_pct = round(overview["mature"] / total * 100) if total else 0
    ui.stat_row([
        {
            "label": "Session",
            "value": f"{done} / {session_size}",
            "hint": f"{overview['due_today']} due in total",
            "accent": True,
        },
        {"label": "Reviewed today", "value": overview["reviewed_today"], "hint": "cards rated"},
        {"label": "Streak", "value": f"{overview['streak']}d", "hint": "days in a row"},
        {
            "label": "Mature",
            "value": f"{mature_pct}%",
            "hint": f"{overview['mature']} of {total} words",
        },
    ])


def _hints(agent, agent_error, word: dict) -> None:
    with st.expander("Ask AI for a hint"):
        if agent is None:
            st.info(f"AI hints unavailable: {agent_error}")
            return

        preset_key = f"hint_preset_{word['id']}"
        cols = st.columns(len(QUICK_QUESTIONS))
        for col, (label, prompt) in zip(cols, QUICK_QUESTIONS.items(), strict=True):
            if col.button(label, key=f"{preset_key}_{label}", width="stretch"):
                st.session_state[preset_key] = prompt

        typed = st.text_input("Or ask your own question", key=f"hint_q_{word['id']}")
        question = typed.strip() or st.session_state.get(preset_key, "")
        if not question:
            return

        cache_key = f"hint_cache_{word['id']}_{question}"
        if cache_key not in st.session_state:
            with st.spinner("Thinking..."):
                try:
                    st.session_state[cache_key] = ai_mod.get_hint(
                        agent, word["dutch"], word["word_type"], word["english"], question
                    )
                except Exception as exc:  # noqa: BLE001 - a failed hint must not lose the review
                    st.error(f"Hint failed: {exc}")
                    return
        st.caption(question)
        st.markdown(st.session_state[cache_key])


def _study(agent_result) -> None:
    agent, agent_error = agent_result
    _load_session()

    session_size = st.session_state.session_size
    remaining = len(st.session_state.queue) - st.session_state.card_idx

    if session_size == 0:
        st.success("Nothing due right now. Enjoy the day off.")
        return

    if remaining <= 0:
        st.success(f"Daily goal reached — {session_size} cards reviewed.")
        if st.button("Study more", width="stretch"):
            _reset_session()
            st.rerun()
        return

    done = session_size - remaining
    st.progress(done / session_size, text=f"{done} of {session_size} cards")

    reverse = st.session_state.get("reverse_mode", False)
    card = st.session_state.queue[st.session_state.card_idx]
    word = card["word"]
    front, back = (
        (word["english"], word["dutch"]) if reverse else (word["dutch"], word["english"])
    )
    tag = " · ".join(part for part in [word["word_type"], word["chapter"]] if part)
    meta = (
        f"seen {card['reps']}× · interval {_format_days(card['interval'])} · "
        f"ease {card['ease_factor']:.2f}"
        if card["reps"]
        else "new card"
    )

    ui.flashcard(
        front=front,
        tag=tag,
        back=back if st.session_state.flipped else None,
        meta=meta,
    )

    audio_path = MEDIA_DIR / word["audio_file"] if word["audio_file"] else None
    if audio_path and audio_path.exists() and st.session_state.flipped:
        st.audio(str(audio_path))

    if not st.session_state.flipped:
        col1, col2 = st.columns([3, 1])
        if col1.button("Show answer", type="primary", width="stretch"):
            st.session_state.flipped = True
            st.rerun()
        if col2.button("Skip", width="stretch"):
            _skip_current()
            st.rerun()
        _hints(agent, agent_error, word)
        return

    cols = st.columns(len(RATINGS))
    for col, (label, quality) in zip(cols, RATINGS.items(), strict=True):
        preview = card["previews"][PREVIEW_KEYS[label]]
        with col:
            if st.button(
                f"{label} · {_format_days(preview)}",
                key=f"rate_{label}",
                width="stretch",
            ):
                try:
                    api.submit_review(word["id"], quality)
                except api.ApiError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.card_idx += 1
                    st.session_state.flipped = False
                    st.rerun()

    _hints(agent, agent_error, word)


def _activity_chart() -> None:
    data = pd.DataFrame(api.activity(days=21))
    data["date"] = pd.to_datetime(data["date"])
    chart = (
        alt.Chart(data)
        .mark_bar(size=11, cornerRadiusEnd=3, color="#f2660a")
        .encode(
            x=alt.X(
                "date:T",
                title=None,
                scale=alt.Scale(padding=18),
                axis=alt.Axis(format="%b %d", grid=False),
            ),
            y=alt.Y("reviews:Q", title=None, axis=alt.Axis(grid=True, tickMinStep=1)),
            tooltip=[
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("reviews:Q", title="Reviews"),
            ],
        )
        .properties(height=170)
    )
    st.altair_chart(chart, width="stretch")


def _forecast_chart() -> None:
    points = api.forecast(days=15)
    backlog = points[0]["cards"]
    # Today's backlog can be thousands of cards and would flatten the rest of the curve.
    data = pd.DataFrame(points[1:])
    data["date"] = pd.to_datetime(data["date"])
    chart = (
        alt.Chart(data)
        .mark_area(
            line={"color": "#5b8def"},
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color="rgba(91,141,239,0.45)", offset=0),
                    alt.GradientStop(color="rgba(91,141,239,0.02)", offset=1),
                ],
                x1=1, x2=1, y1=1, y2=0,
            ),
            interpolate="monotone",
        )
        .encode(
            x=alt.X("date:T", title=None, axis=alt.Axis(format="%b %d", grid=False)),
            y=alt.Y("cards:Q", title=None),
            tooltip=[alt.Tooltip("date:T", title="Date"), alt.Tooltip("cards:Q", title="Cards")],
        )
        .properties(height=170)
    )
    st.altair_chart(chart, width="stretch")
    if backlog:
        st.caption(f"Plus {backlog} card(s) already due today.")


def _progress(overview: dict) -> None:
    ui.section("Review activity — last 21 days")
    _activity_chart()

    ui.section("Coming up — next 14 days")
    _forecast_chart()

    ui.section("Word maturity")
    ui.stat_row([
        {"label": "New", "value": overview["new"], "hint": "never reviewed"},
        {"label": "Learning", "value": overview["learning"], "hint": "under 21 days"},
        {"label": "Mature", "value": overview["mature"], "hint": "21 days or more"},
        {"label": "Reviews", "value": overview["total_reviews"], "hint": "all time"},
    ])

    breakdown = api.chapters()
    if breakdown:
        with st.expander(f"By chapter ({len(breakdown)})"):
            st.dataframe(
                [
                    {
                        "Chapter": row["chapter"],
                        "Words": row["words"],
                        "Reviews": row["reviews"] or 0,
                    }
                    for row in breakdown
                ],
                width="stretch",
                hide_index=True,
            )


def _session_controls() -> None:
    """Sidebar controls. Runs before the queue is built so changes apply immediately."""
    with st.sidebar:
        st.markdown("### Session")
        goal = st.select_slider(
            "Cards per day",
            options=DAILY_GOAL_OPTIONS,
            value=DEFAULT_DAILY_GOAL,
            key="daily_goal",
        )
        if goal != st.session_state.get("active_goal", goal):
            _reset_session()
        st.session_state.active_goal = goal

        st.toggle("Reverse (English → Dutch)", key="reverse_mode")
        if st.button("Restart session", width="stretch"):
            _reset_session()
            st.rerun()


def render(agent_result) -> None:
    overview = api.overview()

    ui.inject_css(rating_keys={label: f"rate_{label}" for label in RATINGS})
    _session_controls()

    ui.header("Vocabulary", f"{overview['total_words']} Dutch words · spaced repetition")
    _load_session()
    _snapshot(overview)

    study_tab, progress_tab = st.tabs(["Study", "Progress"])
    with study_tab:
        _study(agent_result)
    with progress_tab:
        _progress(overview)
