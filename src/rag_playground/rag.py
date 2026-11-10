"""The two ways to answer from the campaign: retrieve-then-answer, or let the model search."""

import os
from collections.abc import Callable

from pydantic_ai import Agent as PydanticAgent
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel

from ai_playground.agent import DEFAULT_MODEL
from ai_playground.agent import Agent as PlaygroundAgent
from rag_playground.index import Index, ollama

RULES = """
Answer only from campaign excerpts. Each excerpt starts with the chapter or section it comes
from; mention that chapter when you use it. If the excerpts do not contain the answer, say so
instead of guessing.
"""

AGENTIC_CONTEXT = (
    """
You answer questions about the user's own Dungeons & Dragons campaign, which is written down
as a long first-person story with world-building sections. You know nothing about it except
what the search_campaign tool returns, so call it before answering, and call it again with
different words (a name, a place, an event) when the first results are not enough. Do not
use web search for campaign questions.
"""
    + RULES
)


def model_name() -> str:
    return os.getenv("PLAYGROUND_MODEL") or DEFAULT_MODEL


def sources(chunks: list[str]) -> str:
    """The distinct section titles of `chunks`, in the order they were retrieved."""
    return "; ".join(dict.fromkeys(chunk.partition("\n")[0] for chunk in chunks))


def two_step(index: Index, question: str, model: Model | str | None = None, k: int = 5) -> str:
    """Classic RAG: always retrieve once, then answer with the excerpts in the prompt."""
    found = index.search(question, k)
    print(f"  [retrieved: {sources(found)}]")
    model = model or OpenAIChatModel(model_name(), provider=ollama())
    agent = PydanticAgent(model, system_prompt="You answer questions about a D&D campaign." + RULES)
    excerpts = "\n\n---\n\n".join(found)
    return agent.run_sync(f"Excerpts:\n\n{excerpts}\n\nQuestion: {question}").output


def search_tool(index: Index) -> Callable[[str], str]:
    def search_campaign(query: str) -> str:
        """Search the user's D&D campaign story and world-building notes.

        Returns the passages closest in meaning to `query`, each starting with the chapter
        or section it comes from. Search for one thing at a time: a character, a place, an
        event. Call it several times to follow a thread across chapters.
        """
        found = index.search(query)
        print(f"  [search_campaign({query!r}) -> {sources(found)}]")
        return "\n\n---\n\n".join(found)

    return search_campaign


def agentic(index: Index, model: Model | str | None = None) -> PlaygroundAgent:
    """Agentic RAG: the playground agent, with retrieval as a tool it chooses to call."""
    return PlaygroundAgent(
        model or model_name(), extra_context=AGENTIC_CONTEXT, extra_tools=[search_tool(index)]
    )
