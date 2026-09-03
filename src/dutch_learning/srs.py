from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class SRSState:
    word_id: int
    interval: int
    ease_factor: float
    due_date: date
    reps: int


def new_state(word_id: int) -> SRSState:
    return SRSState(
        word_id=word_id,
        interval=1,
        ease_factor=2.5,
        due_date=date.today(),
        reps=0,
    )


def update_sm2(state: SRSState, quality: int) -> SRSState:
    ease = state.ease_factor + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    ease = max(1.3, ease)

    if quality < 3:
        reps = 0
        interval = 1
    else:
        reps = state.reps + 1
        if state.reps == 0:
            interval = 1
        elif state.reps == 1:
            interval = 6
        else:
            interval = round(state.interval * state.ease_factor)

    return SRSState(
        word_id=state.word_id,
        interval=interval,
        ease_factor=ease,
        due_date=date.today() + timedelta(days=interval),
        reps=reps,
    )
