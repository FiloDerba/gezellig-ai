"""A small knowledge graph of the campaign: which named things are related, and how.

A chat model reads every chunk once and writes down the relations it states. They are kept
in a JSON file next to the index and looked up by name at question time, with no model.
"""

import hashlib
import json
import os
import re
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent, UnexpectedModelBehavior
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.settings import ModelSettings

from ai_playground.agent import DEFAULT_MODEL
from rag_playground.index import doc_path, ollama

PROMPT = """
You extract a knowledge graph from one excerpt of a Dungeons & Dragons campaign, written as a
first-person story with world-building sections. The first line of the excerpt is its chapter.

Return the relations between named entities (characters, places, factions, gods, items,
events) that the excerpt states. Rules:
- Use names exactly as written. Skip anything that has no name ("the guard", "a city").
- In a first-person excerpt the narrator ("I", "me") is written as "the narrator", unless the
  excerpt gives their name. World-building sections have no narrator: never use it there.
- `relation` is a short phrase in the present tense: "lives in", "leads", "is the brother of".
- Both ends must be names. Never use a relation as a way to describe one entity.
- Keep lasting facts: who someone is, family, allegiance, rank, where a place is, who rules
  it, who killed, betrayed, created or imprisoned whom. Skip moment-to-moment action
  (walking, talking, blows in a fight) and feelings.
- Only relations the text states. No guesses, no general knowledge. Many excerpts are pure
  action and have none: return an empty list for those.
- `quote` is the one sentence of the excerpt that states the relation, copied word for word.
  Leave the relation out if no sentence states it.
"""

FIRST_PERSON = re.compile(r"\b(I|me|my|we|us|our)\b")
QUOTES = str.maketrans("‘’“”", "''\"\"")


class Relation(BaseModel):
    source: str = Field(description="Named entity the relation starts from")
    relation: str = Field(description="Short phrase, present tense")
    target: str = Field(description="Named entity the relation points to")
    quote: str = Field(description="Sentence of the excerpt that states it, word for word")


Extractor = Agent[None, list[Relation]]


def extractor(model: Model | str | None = None) -> Extractor:
    """The agent that reads one chunk and returns its relations."""
    if not isinstance(model, Model):
        name = model or os.getenv("RAG_GRAPH_MODEL") or DEFAULT_MODEL
        model = OpenAIChatModel(name, provider=ollama())
    # Thinking off: about 11 s a chunk over the whole campaign, against 40 s and more with it
    # on in a trial, and with cleaner output.
    # shortcut: assumes an Ollama model that accepts this setting; drop it for other providers.
    settings = ModelSettings(extra_body={"reasoning_effort": "none"})
    return Agent(model, system_prompt=PROMPT, output_type=list[Relation], model_settings=settings)


def extract(agent: Extractor, chunk: str) -> list[Relation]:
    return agent.run_sync(chunk).output


def _plain(text: str) -> str:
    """Lower case, straight quotes, single spaces: how names and quotes are compared to text."""
    return " ".join(text.translate(QUOTES).casefold().split())


def stated(relation: Relation, chunk: str) -> bool:
    """Whether `chunk` backs the relation: it contains the quote and both names.

    This drops relations the model made up, ends that are not names ("unknown", "a burial
    site") and a narrator in text that has none. It does not check that the quote means
    what the relation says.
    """
    text = _plain(chunk)
    names = {_plain(relation.source), _plain(relation.target)}
    if FIRST_PERSON.search(chunk):
        names.discard("the narrator")  # the one name that is not written in the text
    # The model shortens long sentences with "...": every piece it kept must be in the text.
    pieces = [piece.strip() for piece in re.split(r"\.\.\.|…", _plain(relation.quote))]
    return any(pieces) and all(piece in text for piece in pieces + sorted(names))


class Graph:
    def __init__(self, relations: list[dict[str, str]]):
        """`relations` are dicts: source, relation, target, the quote that states it, section."""
        self.relations = relations

    def about(self, name: str) -> list[dict[str, str]]:
        """Relations with `name` at either end, each distinct one once, in story order."""
        # shortcut: plain substring match, so two spellings of a name stay two entities;
        # merge aliases at extraction time if that starts to hide answers.
        wanted = name.casefold().strip()
        found = {}
        for row in self.relations:
            if wanted in row["source"].casefold() or wanted in row["target"].casefold():
                key = (
                    row["source"].casefold(),
                    row["relation"].casefold(),
                    row["target"].casefold(),
                )
                found.setdefault(key, row)
        return list(found.values())


def load_graph(
    chunks: list[str], doc: str | Path | None = None, agent: Extractor | None = None
) -> Graph:
    """The graph for `chunks`, extracted on first use and reused until they, the model or the
    prompt change.

    Relations the chunk does not back (see `stated`) are left out. Progress is saved after
    every chunk, so an interrupted run continues where it stopped.
    """
    agent = agent or extractor()
    name = getattr(agent.model, "model_name", agent.model)
    key = f"{name}:{hashlib.sha256(chr(0).join([PROMPT, *chunks]).encode()).hexdigest()}"
    cache = doc_path(doc).with_suffix(".graph.json")
    saved = json.loads(cache.read_text()) if cache.exists() else {}
    if saved.get("key") != key:
        saved = {"key": key, "done": 0, "relations": []}
    if saved["done"] == len(chunks):
        return Graph(saved["relations"])

    skipped = dropped = 0
    for number, chunk in enumerate(chunks[saved["done"] :], start=saved["done"]):
        print(f"\rExtracting relations {number}/{len(chunks)} chunks...", end="", flush=True)
        section = chunk.partition("\n")[0]
        try:
            found = extract(agent, chunk)
        except UnexpectedModelBehavior:  # the model's output was not usable: leave this chunk out
            found, skipped = [], skipped + 1
        backed = [relation for relation in found if stated(relation, chunk)]
        dropped += len(found) - len(backed)
        saved["relations"] += [{**relation.model_dump(), "section": section} for relation in backed]
        saved["done"] = number + 1
        partial = cache.with_suffix(".tmp")
        partial.write_text(json.dumps(saved))
        partial.replace(cache)  # never leaves a half-written file behind
    note = f" ({skipped} chunks skipped, {dropped} relations dropped as not in the text)"
    print(f"\rExtracted {len(saved['relations'])} relations from {len(chunks)} chunks{note}.    ")
    return Graph(saved["relations"])
