from datetime import date, timedelta
from dutch_learning.srs import SRSState, update_sm2, new_state


def _state(interval=1, ease_factor=2.5, reps=0, due=None):
    return SRSState(
        word_id=1,
        interval=interval,
        ease_factor=ease_factor,
        due_date=due or date.today(),
        reps=reps,
    )


def test_new_state_due_today():
    s = new_state(word_id=42)
    assert s.word_id == 42
    assert s.due_date == date.today()
    assert s.interval == 1
    assert s.ease_factor == 2.5
    assert s.reps == 0


def test_again_resets_reps_and_short_interval():
    s = _state(interval=10, ease_factor=2.5, reps=5)
    new = update_sm2(s, quality=0)
    assert new.reps == 0
    assert new.interval == 1
    assert new.due_date == date.today() + timedelta(days=1)


def test_hard_resets_reps():
    s = _state(interval=10, ease_factor=2.5, reps=5)
    new = update_sm2(s, quality=1)
    assert new.reps == 0
    assert new.interval == 1


def test_good_first_rep_gives_interval_1():
    s = _state(reps=0)
    new = update_sm2(s, quality=3)
    assert new.interval == 1
    assert new.reps == 1


def test_good_second_rep_gives_interval_6():
    s = _state(reps=1, interval=1)
    new = update_sm2(s, quality=3)
    assert new.interval == 6
    assert new.reps == 2


def test_good_third_rep_multiplies_by_ease():
    s = _state(reps=2, interval=6, ease_factor=2.5)
    new = update_sm2(s, quality=3)
    assert new.interval == round(6 * 2.5)
    assert new.reps == 3


def test_easy_increases_ease_factor():
    s = _state(reps=2, interval=6, ease_factor=2.5)
    new = update_sm2(s, quality=5)
    assert new.ease_factor > s.ease_factor


def test_again_decreases_ease_factor():
    s = _state(ease_factor=2.5)
    new = update_sm2(s, quality=0)
    assert new.ease_factor < s.ease_factor


def test_ease_factor_floor_is_1_3():
    s = _state(ease_factor=1.3)
    new = update_sm2(s, quality=0)
    assert new.ease_factor >= 1.3


def test_due_date_set_correctly_after_good():
    s = _state(reps=2, interval=6, ease_factor=2.5)
    new = update_sm2(s, quality=3)
    assert new.due_date == date.today() + timedelta(days=new.interval)
