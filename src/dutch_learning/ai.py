"""Gemini-backed tutoring: word coaching, free-form hints and pronunciation scoring.

Each agent has its own output type, so the UI gets fields it can lay out rather than a
wall of prose it has to render blindly.
"""

from pydantic import BaseModel, Field
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models import Model

DEFAULT_MODEL = "google:gemini-3.6-flash"

TUTOR_PROMPT = (
    "You are a Dutch language tutor for an English speaker. Be concise and concrete. "
    "Prefer everyday, modern Dutch. Never pad answers with pleasantries."
)

COACH_PROMPT = (
    f"{TUTOR_PROMPT} Explain one word at a time: what it really means, how it is used, "
    "and what an English speaker typically gets wrong about it."
)

HINT_PROMPT = (
    f"{TUTOR_PROMPT} The learner is mid-review and still trying to recall the word, so "
    "nudge them towards it. Do not state the English translation unless they ask outright."
)

PRONUNCIATION_PROMPT = (
    "You are a Dutch pronunciation coach. You will hear a learner say a single Dutch word "
    "or phrase. Judge only pronunciation, not recording quality. Be encouraging but honest, "
    "and describe sounds in terms an English speaker can act on. Dutch sounds worth "
    "attention: the guttural 'g'/'ch', 'ui', 'eu', 'ij'/'ei', and the fact that final 'n' "
    "in '-en' endings is usually dropped in speech."
)


class WordInsight(BaseModel):
    """A structured deep-dive on a single word."""

    meaning: str = Field(description="What the word means, including nuance, in one or two lines")
    example_dutch: str = Field(description="One natural Dutch sentence using the word")
    example_english: str = Field(description="Translation of that sentence")
    mnemonic: str = Field(description="A memory hook an English speaker can actually use")
    pitfall: str = Field(description="The mistake English speakers usually make with this word")


class Pronunciation(BaseModel):
    """Feedback on a recorded attempt at saying a word."""

    score: int = Field(ge=0, le=100, description="How close the attempt is to natural Dutch")
    heard: str = Field(description="What the learner actually seemed to say")
    verdict: str = Field(description="One short sentence of overall judgement")
    strengths: list[str] = Field(default_factory=list, description="Up to two things done well")
    fixes: list[str] = Field(default_factory=list, description="Up to three concrete corrections")


def make_agent(model: Model | str = DEFAULT_MODEL) -> Agent[None, str]:
    return Agent(model, system_prompt=HINT_PROMPT)


def make_coach(model: Model | str = DEFAULT_MODEL) -> Agent[None, WordInsight]:
    return Agent(model, system_prompt=COACH_PROMPT, output_type=WordInsight)


def make_pronunciation_coach(model: Model | str = DEFAULT_MODEL) -> Agent[None, Pronunciation]:
    return Agent(model, system_prompt=PRONUNCIATION_PROMPT, output_type=Pronunciation)


def _describe(dutch: str, word_type: str, english: str) -> str:
    kind = f" ({word_type})" if word_type else ""
    return f"the Dutch word '{dutch}'{kind}, which means '{english}'"


def ask(agent: Agent[None, str], dutch: str, word_type: str, english: str, question: str) -> str:
    """Free-form question about the word the learner is looking at."""
    result = agent.run_sync(
        f"The learner is studying {_describe(dutch, word_type, english)}.\n"
        f"Their question: {question}"
    )
    return result.output


def insight(
    agent: Agent[None, WordInsight], dutch: str, word_type: str, english: str
) -> WordInsight:
    return agent.run_sync(f"Break down {_describe(dutch, word_type, english)}.").output


def score_pronunciation(
    agent: Agent[None, Pronunciation],
    audio: bytes,
    dutch: str,
    english: str,
    media_type: str = "audio/wav",
) -> Pronunciation:
    """Rate a recording of the learner saying `dutch`."""
    result = agent.run_sync(
        [
            f"The learner is trying to say the Dutch word '{dutch}' (meaning '{english}'). "
            "Score the attempt and say what to change.",
            BinaryContent(data=audio, media_type=media_type),
        ]
    )
    return result.output
