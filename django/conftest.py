from datetime import date, timedelta

import pytest

from vocabulary.models import SrsState, Word


@pytest.fixture
def word(db) -> Word:
    """A single new card, due today."""
    instance = Word.objects.create(
        dutch="lezen", english="to read", word_type="verb", chapter="Thema01a"
    )
    SrsState.objects.create(word=instance, due_date=date.today())
    return instance


@pytest.fixture
def make_card(db):
    """Factory for a word plus scheduling state, so tests can set up a queue."""

    def _make(
        dutch="woord",
        english="word",
        chapter="Thema01a",
        word_type="noun",
        audio_file=None,
        reps=0,
        interval=1,
        due_offset=0,
    ):
        instance = Word.objects.create(
            dutch=dutch,
            english=english,
            word_type=word_type,
            chapter=chapter,
            audio_file=audio_file,
        )
        SrsState.objects.create(
            word=instance,
            reps=reps,
            interval=interval,
            due_date=date.today() + timedelta(days=due_offset),
        )
        return instance

    return _make
