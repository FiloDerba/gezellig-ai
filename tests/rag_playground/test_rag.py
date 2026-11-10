import zipfile

import numpy as np
import pytest
from pydantic_ai import Embedder
from pydantic_ai.embeddings import TestEmbeddingModel
from pydantic_ai.models.test import TestModel

from rag_playground import loader, rag
from rag_playground.index import Index, lance_table, load_index, top_k

NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def make_docx(path, paragraphs):
    """A minimal .docx: (style, text) pairs, style "" for body text."""
    body = "".join(
        f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>'
        if style
        else f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
        for style, text in paragraphs
    )
    with zipfile.ZipFile(path, "w") as docx:
        docx.writestr(
            "word/document.xml", f'<w:document xmlns:w="{NS}"><w:body>{body}</w:body></w:document>'
        )
    return path


DOC = [
    ("", "TITLE PAGE"),
    ("Inhopg1", "History5"),
    ("Inhopg1", "Chapter 1: A temple12"),
    ("SamKop", "History"),
    ("Samkop2", "The first age"),
    ("", "Long ago."),
    ("SamKop", "Chapter 1: A temple"),
    ("", "one two three"),
    ("", "four five six"),
    ("", "seven eight nine"),
    ("SamKop", "Chapter 2: Not written yet"),
]


def test_chunks_split_on_headings_and_skip_toc_and_title_page(tmp_path):
    chunks = loader.chunks(make_docx(tmp_path / "c.docx", DOC), max_words=6)
    assert chunks == [
        "History > The first age\nLong ago.",
        "Chapter 1: A temple\none two three\nfour five six",
        "Chapter 1: A temple\nseven eight nine",
    ]


def test_top_k_orders_by_similarity():
    vectors = np.array([[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]], dtype=np.float32)
    assert top_k(vectors, np.array([0.0, 1.0], dtype=np.float32), 2) == [1, 2]


@pytest.mark.parametrize("store", ["lancedb", "numpy"])
def test_load_index_embeds_once_then_reuses_the_cache(tmp_path, capsys, store):
    doc = make_docx(tmp_path / "c.docx", DOC)
    embedder = Embedder(TestEmbeddingModel())
    first = load_index(doc, embedder, store)
    assert "Embedded 2 chunks" in capsys.readouterr().out
    second = load_index(doc, embedder, store)
    assert capsys.readouterr().out == ""
    assert second.store == store
    assert second.chunks == first.chunks
    assert len(second.search("temple", k=1)) == 1


def test_load_index_rejects_an_unknown_store(tmp_path):
    with pytest.raises(ValueError, match="RAG_STORE"):
        load_index(make_docx(tmp_path / "c.docx", DOC), Embedder(TestEmbeddingModel()), "redis")


def test_lancedb_and_numpy_return_the_same_chunks_in_the_same_order(tmp_path):
    # TestEmbeddingModel embeds every query as all ones, so "near" means close to that.
    raw = np.eye(8, dtype=np.float32)[:4] + np.array([[0.9], [0.1], [0.5], [0.3]], dtype=np.float32)
    vectors = raw / np.linalg.norm(raw, axis=1, keepdims=True)
    chunks = [f"Section {i}\ntext {i}" for i in range(4)]
    embedder = Embedder(TestEmbeddingModel())
    in_numpy = Index(chunks, vectors, embedder).search("anything", k=3)
    in_lancedb = Index(chunks, vectors, embedder, lance_table(tmp_path / "db", chunks, vectors))
    assert in_lancedb.search("anything", k=3) == in_numpy == [chunks[0], chunks[2], chunks[3]]


def test_sources_lists_each_section_once():
    assert rag.sources(["Ch 1\na", "Ch 2\nb", "Ch 1\nc"]) == "Ch 1; Ch 2"


def fake_index() -> Index:
    chunks = ["Chapter 1: A temple\nThe swamp smelled of decay."]
    return Index(chunks, np.ones((1, 8), dtype=np.float32), Embedder(TestEmbeddingModel()))


def test_two_step_retrieves_then_answers(capsys):
    model = TestModel(custom_output_text="ok")
    assert rag.two_step(fake_index(), "What did it smell like?", model) == "ok"
    assert "[retrieved: Chapter 1: A temple]" in capsys.readouterr().out


def test_agentic_agent_calls_search_campaign(capsys):
    agent = rag.agentic(fake_index(), TestModel(call_tools=["search_campaign"]))
    output, _ = agent.run("Where was the temple?")
    assert output
    assert "search_campaign(" in capsys.readouterr().out
