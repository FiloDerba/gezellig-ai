"""Everything the app reads and writes.

Importing this configures Django and talks to the database named in `django/.env`
directly, so there is no server and no HTTP in the loop. Queries and scheduling rules
stay on the Django side (`vocabulary.selectors` and `vocabulary.services`); this module
only adapts them for the UI.
"""

from dataclasses import dataclass
from datetime import date
from functools import wraps
from pathlib import Path

from django.db import DatabaseError, close_old_connections

from dutch_learning import django_bootstrap  # noqa: F401  configures Django for the imports below
from vocabulary import selectors, services
from vocabulary.models import SrsState, Word
from vocabulary.sample_deck import load_sample_words
from vocabulary.srs import RATING_CHOICES, preview_intervals

MEDIA_DIR = Path("data/media")
MAX_QUEUE = 500

#: Rating label -> SM-2 quality, in the order the answer buttons are shown.
RATINGS = {label: quality for quality, label in RATING_CHOICES}


class DataError(RuntimeError):
    """Raised when the database cannot be reached or a write is rejected."""


def _guard(func):
    """Surface database failures as something the UI can show instead of a traceback."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DatabaseError as exc:
            raise DataError(f"Cannot reach the database: {exc}") from exc

    return wrapper


def begin_run() -> None:
    """Drop connections that timed out since the last rerun. Streamlit has no request cycle."""
    close_old_connections()


@dataclass(frozen=True)
class Overview:
    total_words: int
    due_today: int
    new: int
    learning: int
    mature: int
    total_reviews: int
    reviewed_today: int
    streak: int

    @property
    def mature_pct(self) -> int:
        return round(self.mature / self.total_words * 100) if self.total_words else 0


@dataclass(frozen=True)
class Card:
    """A due card, plus the interval each rating would schedule."""

    state: SrsState
    previews: dict[str, int]

    @property
    def word(self) -> Word:
        return self.state.word

    @property
    def is_new(self) -> bool:
        return self.state.reps == 0

    @property
    def audio_path(self) -> Path | None:
        return audio_path(self.word)


@dataclass(frozen=True)
class Queue:
    due_total: int
    cards: list[Card]


def audio_path(word: Word) -> Path | None:
    """The native recording for a word, when the Anki import brought one along."""
    if not word.audio_file:
        return None
    path = MEDIA_DIR / word.audio_file
    return path if path.exists() else None


def _card(state: SrsState) -> Card:
    return Card(
        state=state,
        previews=preview_intervals(state.interval, state.ease_factor, state.reps),
    )


# --- reads -------------------------------------------------------------------


@_guard
def overview() -> Overview:
    return Overview(**selectors.overview(date.today()))


@_guard
def activity(days: int = 21) -> list[dict]:
    return selectors.activity(date.today(), days=days)


@_guard
def forecast(days: int = 14) -> list[dict]:
    return selectors.forecast(date.today(), days=days)


@_guard
def chapters() -> list[dict]:
    return selectors.chapter_breakdown()


@_guard
def study_queue(limit: int) -> Queue:
    today = date.today()
    limit = max(1, min(limit, MAX_QUEUE))
    return Queue(
        due_total=SrsState.objects.filter(due_date__lte=today).count(),
        cards=[_card(state) for state in selectors.due_queue(today, limit=limit)],
    )


@_guard
def words(
    chapter: str | None = None,
    search: str | None = None,
    maturity: str | None = None,
) -> list[Word]:
    return list(selectors.words(chapter=chapter, search=search, maturity=maturity))


@_guard
def encountered(search: str | None = None, limit: int | None = None) -> list[Word]:
    """Words the learner has rated at least once, annotated with `times_reviewed`/`last_seen`."""
    return list(selectors.encountered(search=search, limit=limit))


@_guard
def speaking_pool(limit: int = 30) -> list[Word]:
    """Words that have a native recording to compare against, due ones first."""
    return list(selectors.speaking_pool(date.today(), limit=limit))


# --- writes ------------------------------------------------------------------


@_guard
def submit_review(word_id: int, quality: int) -> SrsState:
    state = SrsState.objects.select_related("word").get(pk=word_id)
    return services.record_review(state, quality)


@_guard
def add_word(dutch: str, english: str, word_type: str = "", chapter: str = "Custom") -> Word:
    return services.create_word(dutch, english, word_type=word_type, chapter=chapter)


@_guard
def delete_word(word_id: int) -> None:
    Word.objects.filter(pk=word_id).delete()


@_guard
def load_sample_deck() -> int:
    return load_sample_words()
