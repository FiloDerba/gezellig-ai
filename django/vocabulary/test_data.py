"""Tests for `dutch_learning.data`, the layer the Streamlit pages actually call."""

from datetime import date, timedelta

import pytest

from dutch_learning import data
from vocabulary.models import ReviewLog, SrsState


@pytest.mark.django_db
class OverviewTests:
    def test_counts_the_deck(self, make_card):
        make_card(dutch="lezen")
        make_card(dutch="lopen", reps=3, interval=30)
        result = data.overview()
        assert (result.total_words, result.new, result.mature) == (2, 1, 1)

    def test_mature_pct_is_rounded(self, make_card):
        make_card(dutch="a", reps=3, interval=30)
        make_card(dutch="b")
        make_card(dutch="c")
        assert data.overview().mature_pct == 33

    def test_mature_pct_is_zero_for_an_empty_deck(self):
        assert data.overview().mature_pct == 0


@pytest.mark.django_db
class StudyQueueTests:
    def test_returns_due_cards_with_previews(self, word):
        queue = data.study_queue(limit=10)
        assert queue.due_total == 1
        assert set(queue.cards[0].previews) == {"again", "hard", "good", "easy"}

    def test_previews_grow_with_the_rating(self, word):
        previews = data.study_queue(limit=1).cards[0].previews
        assert previews["again"] <= previews["good"] <= previews["easy"]

    def test_limit_caps_the_session_but_not_the_total(self, make_card):
        for index in range(5):
            make_card(dutch=f"woord{index}")
        queue = data.study_queue(limit=2)
        assert (len(queue.cards), queue.due_total) == (2, 5)

    def test_cards_due_later_are_excluded(self, make_card):
        make_card(dutch="later", due_offset=3)
        assert data.study_queue(limit=10).cards == []

    def test_new_cards_come_after_started_ones(self, make_card):
        make_card(dutch="nieuw")
        make_card(dutch="bezig", reps=2)
        first = data.study_queue(limit=10).cards[0]
        assert first.word.dutch == "bezig"
        assert first.is_new is False

    def test_limit_is_capped(self, word):
        assert data.study_queue(limit=10_000).cards  # must not raise


@pytest.mark.django_db
class WordListTests:
    def test_search_matches_dutch_or_english(self, make_card):
        make_card(dutch="lezen", english="to read")
        make_card(dutch="schrijven", english="to write")
        assert [w.dutch for w in data.words(search="read")] == ["lezen"]

    def test_chapter_filter(self, make_card):
        make_card(dutch="een", chapter="Thema01")
        make_card(dutch="twee", chapter="Thema02")
        assert [w.dutch for w in data.words(chapter="Thema02")] == ["twee"]

    def test_maturity_filter_for_new_words(self, make_card):
        make_card(dutch="nieuw")
        make_card(dutch="oud", reps=4)
        assert [w.dutch for w in data.words(maturity="new")] == ["nieuw"]

    def test_returns_everything_without_pagination(self, make_card):
        for index in range(120):
            make_card(dutch=f"woord{index}")
        assert len(data.words()) == 120


@pytest.mark.django_db
class SpeakingPoolTests:
    def test_only_words_with_audio(self, make_card):
        make_card(dutch="met", audio_file="met.mp3")
        make_card(dutch="zonder")
        assert [w.dutch for w in data.speaking_pool()] == ["met"]

    def test_empty_audio_string_does_not_count(self, make_card):
        make_card(dutch="leeg", audio_file="")
        assert data.speaking_pool() == []

    def test_due_words_come_first(self, make_card):
        make_card(dutch="later", audio_file="a.mp3", due_offset=5)
        make_card(dutch="nu", audio_file="b.mp3")
        assert data.speaking_pool()[0].dutch == "nu"

    def test_audio_path_is_none_when_the_file_is_missing(self, make_card):
        word = make_card(dutch="spook", audio_file="does-not-exist.mp3")
        assert data.audio_path(word) is None

    def test_audio_path_points_at_the_media_dir(self, make_card, tmp_path, monkeypatch):
        monkeypatch.setattr(data, "MEDIA_DIR", tmp_path)
        (tmp_path / "echt.mp3").write_bytes(b"audio")
        word = make_card(dutch="echt", audio_file="echt.mp3")
        assert data.audio_path(word) == tmp_path / "echt.mp3"


@pytest.mark.django_db
class WriteTests:
    def test_submit_review_reschedules_and_logs(self, word):
        state = data.submit_review(word.id, 3)
        assert state.reps == 1
        assert state.due_date > date.today()
        assert ReviewLog.objects.filter(word=word).count() == 1

    def test_again_sends_the_card_back_to_tomorrow(self, make_card):
        card = make_card(dutch="moeilijk", reps=5, interval=40)
        state = data.submit_review(card.id, 0)
        assert (state.reps, state.due_date) == (0, date.today() + timedelta(days=1))

    def test_add_word_creates_its_schedule(self):
        word = data.add_word("fietsen", "to cycle", "verb", "Custom")
        assert SrsState.objects.get(word=word).due_date == date.today()

    def test_delete_word_removes_it(self, word):
        data.delete_word(word.id)
        assert data.words() == []

    def test_load_sample_deck_is_idempotent(self):
        assert data.load_sample_deck() == 30
        assert data.load_sample_deck() == 0


@pytest.mark.django_db
class ActivityAndForecastTests:
    def test_activity_covers_every_day_in_the_window(self, word):
        assert len(data.activity(days=7)) == 7

    def test_activity_counts_a_review_today(self, word):
        data.submit_review(word.id, 3)
        assert data.activity(days=7)[-1]["reviews"] == 1

    def test_forecast_starts_today(self, word):
        assert data.forecast(days=5)[0]["date"] == date.today()

    def test_chapters_are_grouped(self, make_card):
        make_card(dutch="een", chapter="Thema01")
        make_card(dutch="twee", chapter="Thema01")
        make_card(dutch="drie", chapter="Thema02")
        assert {row["chapter"]: row["words"] for row in data.chapters()} == {
            "Thema01": 2,
            "Thema02": 1,
        }


class RatingTests:
    def test_ratings_are_ordered_from_worst_to_best(self):
        assert list(data.RATINGS) == ["Again", "Hard", "Good", "Easy"]
        assert list(data.RATINGS.values()) == sorted(data.RATINGS.values())
