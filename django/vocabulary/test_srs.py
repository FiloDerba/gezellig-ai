from datetime import date, timedelta

from vocabulary.srs import (
    AGAIN,
    EASY,
    EASY_BONUS,
    EASY_FIRST_INTERVAL,
    GOOD,
    HARD,
    HARD_MULTIPLIER,
    HARD_SECOND_INTERVAL,
    MAX_INTERVAL_DAYS,
    MIN_EASE_FACTOR,
    SECOND_INTERVAL,
    initial_schedule,
    preview_intervals,
    review,
)

TODAY = date.today()


class InitialScheduleTests:
    def test_new_card_is_due_today(self):
        schedule = initial_schedule(TODAY)
        assert (schedule.interval, schedule.ease_factor, schedule.reps) == (1, 2.5, 0)
        assert schedule.due_date == TODAY


class LapseTests:
    def test_again_resets_reps_to_one_day(self):
        schedule = review(interval=40, ease_factor=2.5, reps=5, quality=AGAIN, today=TODAY)
        assert (schedule.interval, schedule.reps) == (1, 0)
        assert schedule.due_date == TODAY + timedelta(days=1)

    def test_again_lowers_ease(self):
        assert review(10, 2.5, 3, AGAIN, TODAY).ease_factor < 2.5

    def test_ease_never_drops_below_the_floor(self):
        assert review(10, MIN_EASE_FACTOR, 3, AGAIN, TODAY).ease_factor == MIN_EASE_FACTOR


class LearningStepTests:
    def test_good_graduates_to_one_day(self):
        schedule = review(1, 2.5, 0, GOOD, TODAY)
        assert (schedule.interval, schedule.reps) == (1, 1)

    def test_easy_graduates_further(self):
        assert review(1, 2.5, 0, EASY, TODAY).interval == EASY_FIRST_INTERVAL

    def test_second_good_review_gives_six_days(self):
        assert review(1, 2.5, 1, GOOD, TODAY).interval == SECOND_INTERVAL

    def test_second_hard_review_is_shorter(self):
        assert review(1, 2.5, 1, HARD, TODAY).interval == HARD_SECOND_INTERVAL

    def test_second_easy_review_gets_bonus(self):
        assert review(1, 2.5, 1, EASY, TODAY).interval == round(SECOND_INTERVAL * EASY_BONUS)


class ReviewStepTests:
    def test_good_multiplies_by_ease(self):
        assert review(6, 2.5, 2, GOOD, TODAY).interval == round(6 * 2.5)

    def test_hard_keeps_progress_and_grows_slowly(self):
        schedule = review(10, 2.5, 5, HARD, TODAY)
        assert schedule.reps == 6
        assert schedule.interval == round(10 * HARD_MULTIPLIER)
        assert schedule.ease_factor < 2.5

    def test_easy_applies_bonus_over_ease(self):
        schedule = review(10, 2.5, 3, EASY, TODAY)
        assert schedule.interval == round(10 * schedule.ease_factor * EASY_BONUS)

    def test_review_always_gains_at_least_one_day(self):
        assert review(1, MIN_EASE_FACTOR, 3, HARD, TODAY).interval == 2
        assert review(10, MIN_EASE_FACTOR, 3, GOOD, TODAY).interval > 10

    def test_interval_is_capped(self):
        assert review(MAX_INTERVAL_DAYS, 2.5, 9, EASY, TODAY).interval == MAX_INTERVAL_DAYS

    def test_due_date_follows_the_interval(self):
        schedule = review(6, 2.5, 2, GOOD, TODAY)
        assert schedule.due_date == TODAY + timedelta(days=schedule.interval)


class PreviewTests:
    def test_previews_cover_every_rating(self):
        assert set(preview_intervals(1, 2.5, 0)) == {"again", "hard", "good", "easy"}

    def test_previews_are_ordered_and_distinct_on_a_review_card(self):
        previews = preview_intervals(10, 2.5, 4)
        values = [previews[key] for key in ("again", "hard", "good", "easy")]
        assert values == sorted(values)
        assert len(set(values)) == 4

    def test_easy_beats_good_on_a_new_card(self):
        previews = preview_intervals(1, 2.5, 0)
        assert previews["easy"] > previews["good"]
