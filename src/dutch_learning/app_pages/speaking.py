import streamlit as st

from dutch_learning import ai, data, shared

SCORE_BANDS = [
    (85, "green", "Native-ish"),
    (65, "orange", "Understandable"),
    (0, "red", "Keep at it"),
]


def _band(score: int) -> tuple[str, str]:
    for threshold, colour, label in SCORE_BANDS:
        if score >= threshold:
            return colour, label
    return "red", "Keep at it"


if "speaking_pool" not in st.session_state:
    st.session_state.speaking_pool = data.speaking_pool(limit=30)
    st.session_state.speaking_idx = 0

pool = st.session_state.speaking_pool

if not pool:
    st.info(
        "No words with a native recording yet. Import an Anki deck that ships audio to "
        "practise pronunciation.",
        icon=":material/mic_off:",
    )
    st.stop()

word = pool[st.session_state.speaking_idx % len(pool)]
coach, coach_error = shared.agent("pronunciation")

st.caption("Say the word out loud, then record yourself. Gemini scores the attempt.")

with st.container(border=True):
    with st.container(horizontal=True, horizontal_alignment="center"):
        if word.word_type:
            st.badge(word.word_type, color="gray")
        if word.chapter:
            st.badge(word.chapter, color="gray")

    st.title(word.dutch, text_alignment="center")
    st.caption(word.english, text_alignment="center")

    reference = data.audio_path(word)
    if reference:
        st.caption("Native speaker")
        st.audio(str(reference))

with st.container(horizontal=True):
    if st.button("Next word", icon=":material/skip_next:"):
        st.session_state.speaking_idx += 1
        st.session_state.pop(f"attempt_{word.id}", None)
        st.rerun()
    if st.button("Shuffle pool", icon=":material/shuffle:", width="content"):
        st.session_state.pop("speaking_pool", None)
        st.rerun()

recording = st.audio_input("Record your attempt", key=f"mic_{word.id}")

if recording is None:
    st.stop()

if coach is None:
    st.warning(f"AI scoring unavailable: {coach_error}", icon=":material/warning:")
    st.stop()

attempt_key = f"attempt_{word.id}"
audio_bytes = recording.getvalue()

# Re-scoring the same take on every rerun would be slow and would burn quota.
if st.session_state.get(attempt_key, {}).get("size") != len(audio_bytes):
    with st.spinner("Listening..."):
        try:
            feedback = ai.score_pronunciation(
                coach, audio_bytes, word.dutch, word.english, recording.type or "audio/wav"
            )
        except Exception as exc:  # noqa: BLE001 - a failed call must not break the page
            st.error(f"Could not score that recording: {exc}", icon=":material/error:")
            st.stop()
    st.session_state[attempt_key] = {"size": len(audio_bytes), "feedback": feedback}

feedback = st.session_state[attempt_key]["feedback"]
colour, band = _band(feedback.score)

with st.container(border=True):
    with st.container(horizontal=True):
        st.metric("Score", f"{feedback.score}/100", border=True)
        with st.container():
            st.badge(band, color=colour)
            st.markdown(feedback.verdict)
            st.caption(f"Heard: {feedback.heard}")

    st.progress(feedback.score / 100)

    if feedback.strengths:
        st.markdown("**Working well**")
        for item in feedback.strengths:
            st.markdown(f"- :green[{item}]")

    if feedback.fixes:
        st.markdown("**Focus on**")
        for item in feedback.fixes:
            st.markdown(f"- {item}")
