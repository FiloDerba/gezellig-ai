import altair as alt
import pandas as pd
import streamlit as st

from dutch_learning import data

overview = st.session_state.overview
ACCENT = "#f2660a"

with st.container(horizontal=True):
    st.metric("New", overview.new, help="Never reviewed", border=True)
    st.metric("Learning", overview.learning, help="Interval under 21 days", border=True)
    st.metric("Mature", overview.mature, help="Interval of 21 days or more", border=True)
    st.metric("Reviews", overview.total_reviews, help="All time", border=True)

st.progress(
    overview.mature_pct / 100,
    text=f"{overview.mature_pct}% mature · {overview.mature} of {overview.total_words} words",
)

st.subheader("Review activity", icon=":material/bar_chart:")
st.caption("Last 21 days")

activity = pd.DataFrame(data.activity(days=21))
activity["date"] = pd.to_datetime(activity["date"])
st.altair_chart(
    alt.Chart(activity)
    .mark_bar(size=11, cornerRadiusEnd=3, color=ACCENT)
    .encode(
        x=alt.X("date:T", title=None, scale=alt.Scale(padding=18),
                axis=alt.Axis(format="%b %d", grid=False)),
        y=alt.Y("reviews:Q", title=None, axis=alt.Axis(grid=True, tickMinStep=1)),
        tooltip=[alt.Tooltip("date:T", title="Date"), alt.Tooltip("reviews:Q", title="Reviews")],
    )
    .properties(height=170)
)

st.subheader("Coming up", icon=":material/event_upcoming:")
st.caption("Next 14 days")

points = data.forecast(days=15)
# Today's backlog can be thousands of cards and would flatten the rest of the curve.
backlog = points[0]["cards"]
upcoming = pd.DataFrame(points[1:])
upcoming["date"] = pd.to_datetime(upcoming["date"])
st.altair_chart(
    alt.Chart(upcoming)
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
if backlog:
    st.caption(f"Plus {backlog} card(s) already due today.")

breakdown = data.chapters()
if breakdown:
    with st.expander(f"By chapter ({len(breakdown)})", icon=":material/folder:"):
        st.dataframe(
            [
                {"Chapter": row["chapter"], "Words": row["words"], "Reviews": row["reviews"] or 0}
                for row in breakdown
            ],
            width="stretch",
            hide_index=True,
        )
