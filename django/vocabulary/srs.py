"""Anki-flavoured SM-2 scheduling.

Deliberately free of Django imports so it stays a pure, directly testable function.
"""

from dataclasses import dataclass
from datetime import date, timedelta

MATURE_INTERVAL_DAYS = 21

# Rating scale exposed by the API, mapped onto SM-2 quality values.
AGAIN, HARD, GOOD, EASY = 0, 1, 3, 5

RATING_CHOICES = [
    (AGAIN, "Again"),
    (HARD, "Hard"),
    (GOOD, "Good"),
    (EASY, "Easy"),
]
RATING_LABELS = dict(RATING_CHOICES)

GRADUATING_INTERVAL = 1  # days after the first successful review
EASY_FIRST_INTERVAL = 4  # days when a new card is answered Easy straight away
SECOND_INTERVAL = 6  # days after the second successful review
HARD_SECOND_INTERVAL = 3  # days when that second review was only Hard
HARD_MULTIPLIER = 1.2  # applied instead of the ease factor on a Hard review
EASY_BONUS = 1.3  # applied on top of the ease factor on an Easy review
MIN_EASE_FACTOR = 1.3
MAX_INTERVAL_DAYS = 365 * 5

# How each rating nudges the ease factor, following Anki's defaults.
EASE_DELTA = {AGAIN: -0.20, HARD: -0.15, GOOD: 0.0, EASY: 0.15}


@dataclass(frozen=True)
class Schedule:
    interval: int
    ease_factor: float
    reps: int
    due_date: date


def initial_schedule(today: date | None = None) -> Schedule:
    return Schedule(interval=1, ease_factor=2.5, reps=0, due_date=today or date.today())


def review(
    interval: int,
    ease_factor: float,
    reps: int,
    quality: int,
    today: date | None = None,
) -> Schedule:
    """Next schedule for a card rated `quality`.

    Only `Again` counts as a lapse. `Hard` keeps the card's progress but grows the
    interval slowly, and `Easy` graduates a new card straight to several days and
    earns a bonus on later reviews.
    """
    today = today or date.today()
    ease = max(MIN_EASE_FACTOR, ease_factor + EASE_DELTA.get(quality, 0.0))

    if quality <= AGAIN:
        return Schedule(
            interval=1,
            ease_factor=ease,
            reps=0,
            due_date=today + timedelta(days=1),
        )

    if reps == 0:
        next_interval = EASY_FIRST_INTERVAL if quality >= EASY else GRADUATING_INTERVAL
    elif reps == 1:
        if quality <= HARD:
            next_interval = HARD_SECOND_INTERVAL
        else:
            next_interval = round(SECOND_INTERVAL * (EASY_BONUS if quality >= EASY else 1))
    else:
        if quality <= HARD:
            factor = HARD_MULTIPLIER
        elif quality >= EASY:
            factor = ease * EASY_BONUS
        else:
            factor = ease
        # A review must always earn at least one extra day, or a low ease can stall a card.
        next_interval = max(round(interval * factor), interval + 1)

    return Schedule(
        interval=min(next_interval, MAX_INTERVAL_DAYS),
        ease_factor=ease,
        reps=reps + 1,
        due_date=today + timedelta(days=min(next_interval, MAX_INTERVAL_DAYS)),
    )


def preview_intervals(interval: int, ease_factor: float, reps: int) -> dict[str, int]:
    """Interval each rating would schedule, for showing on the answer buttons."""
    return {
        label.lower(): review(interval, ease_factor, reps, quality).interval
        for quality, label in RATING_CHOICES
    }
