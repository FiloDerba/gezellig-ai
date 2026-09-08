"""The retrieval the assistant uses to ground answers in the learner's own words."""

from datetime import date, timedelta

import pytest

from dutch_learning import data, vocab_tools
from vocabulary.models import ReviewLog


@pytest.fixture
def studied(make_card):
    """Two reviewed words and one the learner has never seen."""
    fiets = make_card(dutch="de fiets", english="the bicycle", chapter="Thema01", reps=2)
    gracht = make_card(dutch="de gracht", english="the canal", chapter="Thema02", reps=1)
    make_card(dutch="de molen", english="the windmill", chapter="Thema03")
    ReviewLog.objects.create(word=fiets, quality=3, reviewed_on=date.today())
    ReviewLog.objects.create(word=fiets, quality=5, reviewed_on=date.today())
    ReviewLog.objects.create(word=gracht, quality=3, reviewed_on=date.today() - timedelta(days=2))
    return fiets, gracht


@pytest.mark.django_db
class EncounteredTests:
    def test_only_reviewed_words_are_returned(self, studied):
        assert [w.dutch for w in data.encountered()] == ["de fiets", "de gracht"]

    def test_a_word_reset_by_again_still_counts(self, make_card):
        """An 'Again' rating sets reps back to 0, but the word has still been encountered."""
        failed = make_card(dutch="moeilijk", english="difficult", reps=0)
        ReviewLog.objects.create(word=failed, quality=0, reviewed_on=date.today())
        assert [w.dutch for w in data.encountered()] == ["moeilijk"]

    def test_most_recently_seen_comes_first(self, studied):
        assert data.encountered()[0].dutch == "de fiets"

    def test_review_counts_are_annotated(self, studied):
        counts = {w.dutch: w.times_reviewed for w in data.encountered()}
        assert counts == {"de fiets": 2, "de gracht": 1}

    def test_last_seen_is_annotated(self, studied):
        assert data.encountered()[0].last_seen == date.today()

    def test_search_matches_dutch_or_english(self, studied):
        assert [w.dutch for w in data.encountered(search="canal")] == ["de gracht"]

    def test_search_does_not_reach_unstudied_words(self, studied):
        assert data.encountered(search="molen") == []

    def test_limit_applies(self, studied):
        assert len(data.encountered(limit=1)) == 1

    def test_empty_deck_returns_nothing(self):
        assert data.encountered() == []


@pytest.mark.django_db
class SearchToolTests:
    def test_lists_studied_words_with_their_stats(self, studied):
        output = vocab_tools.search_my_vocabulary()
        assert "de fiets = the bicycle" in output
        assert "seen 2x" in output

    def test_never_leaks_unstudied_words(self, studied):
        assert "molen" not in vocab_tools.search_my_vocabulary()

    def test_query_narrows_the_result(self, studied):
        output = vocab_tools.search_my_vocabulary("gracht")
        assert "de gracht" in output and "de fiets" not in output

    def test_a_miss_says_so_rather_than_returning_nothing(self, studied):
        assert "may not have met it yet" in vocab_tools.search_my_vocabulary("zeppelin")

    def test_empty_deck_is_explained(self):
        assert "not reviewed any words yet" in vocab_tools.search_my_vocabulary()

    def test_limit_is_capped(self, studied):
        assert vocab_tools.search_my_vocabulary(limit=10_000)  # must not raise

    def test_limit_of_zero_is_lifted_to_one(self, studied):
        assert len(vocab_tools.search_my_vocabulary(limit=0).splitlines()) == 1


@pytest.mark.django_db
class SummaryToolTests:
    def test_reports_studied_against_deck_size(self, studied):
        assert "reviewed 2 distinct words out of 3" in vocab_tools.my_vocabulary_summary()

    def test_lists_the_chapters_touched(self, studied):
        summary = vocab_tools.my_vocabulary_summary()
        assert "Thema01" in summary and "Thema03" not in summary

    def test_works_on_an_empty_deck(self):
        assert "0 distinct words" in vocab_tools.my_vocabulary_summary()


class ToolRegistrationTests:
    def test_both_tools_are_exported(self):
        assert vocab_tools.TOOLS == [
            vocab_tools.search_my_vocabulary,
            vocab_tools.my_vocabulary_summary,
        ]

    def test_tools_have_docstrings_for_the_model(self):
        """pydantic-ai sends the docstring as the tool description."""
        for tool in vocab_tools.TOOLS:
            assert tool.__doc__ and len(tool.__doc__) > 80

    def test_context_tells_the_agent_to_use_them(self):
        for tool in vocab_tools.TOOLS:
            assert tool.__name__ in vocab_tools.CONTEXT
