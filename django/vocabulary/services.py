"""Write-side operations.

Shared by the REST views and by the Streamlit app when it drives the ORM in-process,
so a rating is recorded the same way whichever entry point is used.
"""

from datetime import date

from django.db import transaction

from vocabulary.models import ReviewLog, SrsState, Word
from vocabulary.srs import initial_schedule
from vocabulary.srs import review as apply_review


def attach_schedule(word: Word, today: date | None = None) -> SrsState:
    """Give a freshly created word its starting schedule."""
    schedule = initial_schedule(today)
    return SrsState.objects.create(
        word=word,
        interval=schedule.interval,
        ease_factor=schedule.ease_factor,
        reps=schedule.reps,
        due_date=schedule.due_date,
    )


def create_word(
    dutch: str,
    english: str,
    word_type: str = "",
    chapter: str = "Custom",
    **extra,
) -> Word:
    with transaction.atomic():
        word = Word.objects.create(
            dutch=dutch,
            english=english,
            word_type=word_type,
            chapter=chapter,
            **extra,
        )
        attach_schedule(word)
    return word


def reset_schedule(word: Word, today: date | None = None) -> SrsState:
    """Send a word back to the start of the schedule."""
    schedule = initial_schedule(today)
    state, _ = SrsState.objects.update_or_create(
        word=word,
        defaults={
            "interval": schedule.interval,
            "ease_factor": schedule.ease_factor,
            "reps": schedule.reps,
            "due_date": schedule.due_date,
        },
    )
    return state


def record_review(state: SrsState, quality: int, today: date | None = None) -> SrsState:
    """Apply a rating: reschedule the card and append to the review log."""
    today = today or date.today()
    schedule = apply_review(state.interval, state.ease_factor, state.reps, quality, today)
    with transaction.atomic():
        state.interval = schedule.interval
        state.ease_factor = schedule.ease_factor
        state.reps = schedule.reps
        state.due_date = schedule.due_date
        state.save(update_fields=["interval", "ease_factor", "reps", "due_date", "updated_at"])
        ReviewLog.objects.create(word_id=state.word_id, quality=quality, reviewed_on=today)
    return state
