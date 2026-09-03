"""Shared styling and small presentational helpers for the Streamlit app."""

import html

import streamlit as st

RATING_COLORS = {
    "Again": "#e5484d",
    "Hard": "#e08c00",
    "Good": "#30a46c",
    "Easy": "#3e63dd",
}

_CSS = """
<style>
/* Neutrals derive from the active text colour so the app works in light and dark themes. */
:root {
    --dl-border: color-mix(in srgb, currentColor 14%, transparent);
    --dl-surface: color-mix(in srgb, currentColor 4%, transparent);
    --dl-accent: #f2660a;
}
.dl-muted { opacity: 0.62; }

/* Tighter, more deliberate page rhythm than the Streamlit default. */
.block-container { padding-top: 2.4rem; padding-bottom: 4rem; max-width: 60rem; }
#MainMenu, footer { visibility: hidden; }

.dl-header { margin-bottom: 1.6rem; }
.dl-header h1 {
    font-size: 2.1rem;
    font-weight: 650;
    letter-spacing: -0.02em;
    margin: 0;
}
.dl-header p { opacity: 0.62; margin: 0.3rem 0 0; font-size: 0.95rem; }

.dl-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr));
    gap: 0.7rem;
    margin-bottom: 1.8rem;
}
.dl-stat {
    background: var(--dl-surface);
    border: 1px solid var(--dl-border);
    border-radius: 14px;
    padding: 0.85rem 1rem;
}
.dl-stat-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    opacity: 0.62;
}
.dl-stat-value {
    font-size: 1.65rem;
    font-weight: 620;
    line-height: 1.25;
    font-variant-numeric: tabular-nums;
}
.dl-stat-hint { font-size: 0.74rem; opacity: 0.55; }
.dl-stat-accent .dl-stat-value { color: var(--dl-accent); }

.dl-card {
    background:
        radial-gradient(120% 140% at 50% 0%, rgba(242, 102, 10, 0.13), transparent 62%),
        var(--dl-surface);
    border: 1px solid var(--dl-border);
    border-radius: 22px;
    padding: 2.6rem 1.6rem;
    text-align: center;
    min-height: 15rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.55rem;
}
.dl-card-tag {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.11em;
    opacity: 0.6;
}
.dl-card-front {
    font-size: 2.5rem;
    font-weight: 620;
    letter-spacing: -0.025em;
    line-height: 1.15;
}
.dl-card-divider { width: 2.2rem; height: 1px; background: var(--dl-border); margin: 0.5rem 0; }
.dl-card-back { font-size: 1.5rem; font-weight: 550; color: var(--dl-accent); }
.dl-card-hidden { font-size: 1.4rem; opacity: 0.22; letter-spacing: 0.35em; }
.dl-card-meta { font-size: 0.8rem; opacity: 0.55; }

.dl-section {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    opacity: 0.62;
    margin: 2.2rem 0 0.7rem;
}

.stButton > button { border-radius: 11px; font-weight: 550; }
div[class*="st-key-rate_"] button {
    border-width: 1px;
    background: var(--dl-surface);
}
</style>
"""

_RATING_CSS_TEMPLATE = """
div.st-key-{key} button {{
    color: {color} !important;
    border-color: {color}55 !important;
}}
div.st-key-{key} button:hover {{
    background: {color}1f !important;
    border-color: {color} !important;
}}
"""


def inject_css(rating_keys: dict[str, str] | None = None) -> None:
    """Apply the app stylesheet. `rating_keys` maps a rating label to its widget key."""
    css = _CSS
    if rating_keys:
        rules = "\n".join(
            _RATING_CSS_TEMPLATE.format(key=key, color=RATING_COLORS[label])
            for label, key in rating_keys.items()
            if label in RATING_COLORS
        )
        css += f"<style>{rules}</style>"
    st.markdown(css, unsafe_allow_html=True)


def header(title: str, subtitle: str = "") -> None:
    sub = f"<p>{html.escape(subtitle)}</p>" if subtitle else ""
    st.markdown(
        f'<div class="dl-header"><h1>{html.escape(title)}</h1>{sub}</div>',
        unsafe_allow_html=True,
    )


def stat_row(stats: list[dict]) -> None:
    """Render stat tiles. Each dict takes `label`, `value`, optional `hint` and `accent`."""
    tiles = []
    for stat in stats:
        hint = stat.get("hint", "")
        hint_html = f'<div class="dl-stat-hint">{html.escape(hint)}</div>' if hint else ""
        accent = " dl-stat-accent" if stat.get("accent") else ""
        tiles.append(
            f'<div class="dl-stat{accent}">'
            f'<div class="dl-stat-label">{html.escape(stat["label"])}</div>'
            f'<div class="dl-stat-value">{html.escape(str(stat["value"]))}</div>'
            f"{hint_html}</div>"
        )
    st.markdown(f'<div class="dl-stats">{"".join(tiles)}</div>', unsafe_allow_html=True)


def flashcard(front: str, tag: str = "", back: str | None = None, meta: str = "") -> None:
    """Render the study card. `back` of None keeps the answer hidden."""
    parts = []
    if tag:
        parts.append(f'<div class="dl-card-tag">{html.escape(tag)}</div>')
    parts.append(f'<div class="dl-card-front">{html.escape(front)}</div>')
    parts.append('<div class="dl-card-divider"></div>')
    if back is None:
        parts.append('<div class="dl-card-hidden">•••</div>')
    else:
        parts.append(f'<div class="dl-card-back">{html.escape(back)}</div>')
    if meta:
        parts.append(f'<div class="dl-card-meta">{html.escape(meta)}</div>')
    st.markdown(f'<div class="dl-card">{"".join(parts)}</div>', unsafe_allow_html=True)


def section(label: str) -> None:
    st.markdown(f'<div class="dl-section">{html.escape(label)}</div>', unsafe_allow_html=True)
