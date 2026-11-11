"""The two ways to answer from the campaign: retrieve-then-answer, or let the model search."""

import os
from collections.abc import Callable

from pydantic_ai import Agent as PydanticAgent
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel

from ai_playground.agent import DEFAULT_MODEL
from ai_playground.agent import Agent as PlaygroundAgent
from rag_playground.graph import Graph
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

GRAPH_CONTEXT = """
You also have campaign_relations, a lookup of how named characters, places and factions are
related across the whole story. Use it for questions about connections or overviews, then
use search_campaign to read the passages before you answer.
"""

MAX_RELATIONS = 60  # an entity like the narrator has hundreds; keep the tool result readable


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


def relations_tool(graph: Graph) -> Callable[[str], str]:
    def campaign_relations(name: str) -> str:
        """Look up how one named character, place, faction or item is related to others.

        Returns one line per relation, "A | relation | B (chapter): sentence it comes from",
        gathered from the whole campaign. Judge each relation by its sentence. Pass a single
        name, as it is written in the story.
        """
        found = graph.about(name)
        print(f"  [campaign_relations({name!r}) -> {len(found)} relations]")
        if not found:
            return f"Nothing in the graph about {name!r}. Try search_campaign."
        lines = [
            f"{row['source']} | {row['relation']} | {row['target']} ({row['section']}): "
            f'"{row["quote"]}"'
            for row in found[:MAX_RELATIONS]
        ]
        if len(found) > MAX_RELATIONS:
            lines.append(f"... and {len(found) - MAX_RELATIONS} more")
        if len(same := graph.names(name)) > 1:
            lines.insert(0, f"These names are the same: {', '.join(same)}.")
        return "\n".join(lines)

    return campaign_relations


def agentic(
    index: Index, model: Model | str | None = None, graph: Graph | None = None
) -> PlaygroundAgent:
    """Agentic RAG: the playground agent, with retrieval as a tool it chooses to call.

    With `graph`, it also gets a tool to look up relations between named things.
    """
    tools = [search_tool(index)] + ([relations_tool(graph)] if graph else [])
    context = AGENTIC_CONTEXT + (GRAPH_CONTEXT if graph else "")
    return PlaygroundAgent(model or model_name(), extra_context=context, extra_tools=tools)
