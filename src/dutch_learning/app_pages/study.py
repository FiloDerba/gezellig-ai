import streamlit as st

from dutch_learning import ai, data, shared

overview = st.session_state.overview
shared.load_session()

size = st.session_state.session_size
remaining = len(st.session_state.cards) - st.session_state.card_idx
done = size - remaining

with st.container(horizontal=True):
    st.metric("Session", f"{done}/{size}", help="Cards rated in this session", border=True)
    st.metric("Due today", overview.due_today, border=True)
    st.metric("Reviewed", overview.reviewed_today, help="Cards rated today", border=True)
    st.metric("Streak", f"{overview.streak}d", border=True)

with st.container(horizontal=True, horizontal_alignment="right"):
    with st.popover("Session", icon=":material/tune:"):
        goal = st.select_slider(
            "Cards per day", options=shared.DAILY_GOALS, value=shared.DEFAULT_GOAL, key="daily_goal"
        )
        if goal != st.session_state.get("active_goal", goal):
            shared.reset_session()
            st.rerun()
        st.session_state.active_goal = goal

        st.toggle("Reverse (English to Dutch)", key="reverse_mode")
        st.toggle("Play audio automatically", value=True, key="autoplay_audio")
        if st.button("Restart session", icon=":material/refresh:"):
            shared.reset_session()
            st.rerun()

if size == 0:
    st.success("Nothing due right now. Enjoy the day off.", icon=":material/check_circle:")
    st.stop()

if remaining <= 0:
    st.success(f"Daily goal reached — {size} cards reviewed.", icon=":material/military_tech:")
    if st.button("Study more", type="primary", icon=":material/add:"):
        shared.reset_session()
        st.rerun()
    st.stop()

st.progress(done / size, text=f"{done} of {size} cards")

card = st.session_state.cards[st.session_state.card_idx]
word = card.word
reverse = st.session_state.get("reverse_mode", False)
front, back = (word.english, word.dutch) if reverse else (word.dutch, word.english)

with st.container(border=True):
    tags = [part for part in (word.word_type, word.chapter) if part]
    with st.container(horizontal=True, horizontal_alignment="center"):
        for tag in tags:
            st.badge(tag, color="gray")
        st.badge(
            "New" if card.is_new else f"Seen {card.state.reps}x",
            color="primary" if card.is_new else "gray",
        )

    st.title(front, text_alignment="center")
    if st.session_state.flipped:
        st.header(f":primary[{back}]", text_alignment="center")
    else:
        st.subheader(":gray[· · ·]", text_alignment="center")

    # In reverse mode the recording is the answer, so it waits for the flip. Otherwise it
    # plays as soon as the card appears, once per card rather than on every rerun.
    if card.audio_path and (not reverse or st.session_state.flipped):
        st.audio(
            str(card.audio_path),
            autoplay=shared.autoplay_once(f"study:{st.session_state.card_idx}:{word.id}"),
        )

    if not card.is_new:
        st.caption(
            f"Interval {shared.format_days(card.state.interval)} · "
            f"ease {card.state.ease_factor:.2f}",
            text_alignment="center",
        )

if st.session_state.flipped:
    with st.container(horizontal=True):
        for label, quality in data.RATINGS.items():
            colour = shared.RATING_COLOURS[label]
            preview = shared.format_days(card.previews[label.lower()])
            if st.button(
                f":{colour}[{label}]  \n:gray[{preview}]", key=f"rate_{label}", width="stretch"
            ):
                try:
                    data.submit_review(word.id, quality)
                except data.DataError as exc:
                    st.error(str(exc), icon=":material/error:")
                else:
                    st.session_state.card_idx += 1
                    st.session_state.flipped = False
                    st.rerun()
else:
    with st.container(horizontal=True):
        if st.button("Show answer", type="primary", icon=":material/visibility:"):
            st.session_state.flipped = True
            st.rerun()
        if st.button("Skip", icon=":material/skip_next:", width="content"):
            shared.skip_current()
            st.rerun()

# --- AI coaching --------------------------------------------------------------

coach, coach_error = shared.agent("coach")
hint_agent, hint_error = shared.agent("hint")

with st.expander("Coach", icon=":material/school:"):
    if coach is None:
        st.caption(f"AI unavailable: {coach_error}")
    else:
        insight_key = f"insight_{word.id}"
        if insight_key not in st.session_state and st.button(
            "Break this word down", icon=":material/auto_awesome:", key=f"btn_{insight_key}"
        ):
            with st.spinner("Thinking..."):
                try:
                    st.session_state[insight_key] = ai.insight(
                        coach, word.dutch, word.word_type, word.english
                    )
                except Exception as exc:  # noqa: BLE001 - never lose the review over a hint
                    st.error(f"Coach failed: {exc}", icon=":material/error:")

        found = st.session_state.get(insight_key)
        if found:
            st.markdown(f"**Meaning** · {found.meaning}")
            st.markdown(f"**Example** · {found.example_dutch}")
            st.caption(found.example_english)
            st.markdown(f"**Mnemonic** · {found.mnemonic}")
            st.markdown(f"**Watch out** · {found.pitfall}")

    if hint_agent is not None:
        question = st.chat_input("Ask about this word", key=f"question_{word.id}")
        answer_key = f"answer_{word.id}"
        if question:
            with st.spinner("Thinking..."):
                try:
                    st.session_state[answer_key] = (
                        question,
                        ai.ask(hint_agent, word.dutch, word.word_type, word.english, question),
                    )
                except Exception as exc:  # noqa: BLE001 - never lose the review over a hint
                    st.error(f"Hint failed: {exc}", icon=":material/error:")
        previous = st.session_state.get(answer_key)
        if previous:
            asked, replied = previous
            st.caption(asked)
            st.markdown(replied)
