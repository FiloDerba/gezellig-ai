"""The tutoring layer, exercised against pydantic-ai's TestModel so no tokens are spent."""

import pytest
from pydantic import ValidationError
from pydantic_ai.models.test import TestModel

from dutch_learning import ai


@pytest.fixture
def coach():
    """A real agent wired to TestModel, since building one needs no API key that way."""
    return ai.make_coach(TestModel())


@pytest.fixture
def pronunciation_coach():
    return ai.make_pronunciation_coach(TestModel())


class WordInsightTests:
    def test_returns_every_field_the_ui_renders(self, coach):
        result = ai.insight(coach, "gezellig", "adjective", "cosy")
        assert isinstance(result, ai.WordInsight)
        for field in ("meaning", "example_dutch", "example_english", "mnemonic", "pitfall"):
            assert getattr(result, field) is not None


class PronunciationTests:
    def test_scores_a_recording(self, pronunciation_coach):
        result = ai.score_pronunciation(pronunciation_coach, b"fake-wav", "gracht", "canal")
        assert isinstance(result, ai.Pronunciation)
        assert 0 <= result.score <= 100

    def test_score_is_bounded(self):
        with pytest.raises(ValidationError):
            ai.Pronunciation(score=140, heard="x", verdict="y")

    def test_strengths_and_fixes_default_to_empty(self):
        feedback = ai.Pronunciation(score=50, heard="x", verdict="y")
        assert (feedback.strengths, feedback.fixes) == ([], [])


class HintTests:
    def test_answers_a_question(self):
        agent = ai.make_agent(TestModel(custom_output_text="Think of a canal."))
        assert ai.ask(agent, "gracht", "noun", "canal", "give me a hint") == "Think of a canal."

    def test_hint_prompt_withholds_the_translation(self):
        assert "not state the english translation" in ai.HINT_PROMPT.lower()
