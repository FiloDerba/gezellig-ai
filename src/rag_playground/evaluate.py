"""Measure retrieval: how often each search returns a section that holds the answer.

The eval file sits next to the document (data/rag/<name>.eval.json, git-ignored like the
campaign): a list of {"kind", "question", "pattern", "sections"}. `pattern` is the regex grep
gets, standing in for the one a model would write; a result is a hit when its section title
starts with one of `sections`. Retrieval only: no model answers or judges anything.
"""

import json
import time
from collections.abc import Callable

from dotenv import load_dotenv

from rag_playground import rag
from rag_playground.index import Index, doc_path, load_index

Retriever = Callable[[dict], list[tuple[str, str]]]  # question -> (section title, text) pairs


def by_index(index: Index, k: int = 5) -> Retriever:
    return lambda q: [(chunk.partition("\n")[0], chunk) for chunk in index.search(q["question"], k)]


def by_grep(chunks: list[str]) -> Retriever:
    # What grep_campaign shows the model: the first MAX_MATCHES hits, each with its title.
    return lambda q: [
        (title, f"{title}: {text}") for title, text in rag.grep(chunks, q["pattern"])
    ][: rag.MAX_MATCHES]


def score(questions: list[dict], retrieve: Retriever) -> tuple[list[dict], float, float]:
    """The questions missed, then words returned and milliseconds per question."""
    missed, words, start = [], 0, time.perf_counter()
    for q in questions:
        found = retrieve(q)
        if not any(title.startswith(tuple(q["sections"])) for title, _ in found):
            missed.append(q)
        words += sum(len(text.split()) for _, text in found)
    seconds = time.perf_counter() - start
    return missed, words / len(questions), seconds * 1000 / len(questions)


def main() -> None:
    load_dotenv()
    questions = json.loads(doc_path().with_suffix(".eval.json").read_text())
    hybrid = load_index(hybrid=True)
    # Same table, vector side only: a second load_index would rebuild the table under it.
    vector = Index(hybrid.chunks, hybrid.vectors, hybrid.embedder, hybrid.table)
    modes = {"vector": by_index(vector), "hybrid": by_index(hybrid), "grep": by_grep(vector.chunks)}
    print(f"{len(questions)} questions; hit = an expected section among the results.")
    for name, retrieve in modes.items():
        missed, words, ms = score(questions, retrieve)
        hits = len(questions) - len(missed)
        print(f"{name:7} {hits:2}/{len(questions)} hits {words:6.0f} words {ms:6.1f} ms")
        for q in missed:
            print(f"          missed ({q['kind']}): {q['question']}")
