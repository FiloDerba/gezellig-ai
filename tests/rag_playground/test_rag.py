import zipfile

import numpy as np
import pytest
from pydantic_ai import Embedder, UnexpectedModelBehavior
from pydantic_ai.embeddings import TestEmbeddingModel
from pydantic_ai.models.test import TestModel

from rag_playground import evaluate, graph, loader, rag
from rag_playground.graph import Graph, Relation, load_graph
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


def test_hybrid_search_finds_an_exact_name_the_vector_search_ranks_last(tmp_path):
    raw = np.eye(8, dtype=np.float32)[:4] + np.array([[0.9], [0.1], [0.5], [0.3]], dtype=np.float32)
    vectors = raw / np.linalg.norm(raw, axis=1, keepdims=True)
    chunks = ["Ch 0\nthe swamp", "Ch 1\nthe city of Ksenrae", "Ch 2\nthe road", "Ch 3\nthe sea"]
    embedder = Embedder(TestEmbeddingModel())
    table = lance_table(tmp_path / "db", chunks, vectors)
    assert chunks[1] not in Index(chunks, vectors, embedder, table).search("Ksenrae?", k=2)
    assert chunks[1] in Index(chunks, vectors, embedder, table, hybrid=True).search("Ksenrae?", k=2)


def test_hybrid_search_needs_the_lancedb_store(tmp_path):
    with pytest.raises(ValueError, match="Hybrid"):
        load_index(
            make_docx(tmp_path / "c.docx", DOC), Embedder(TestEmbeddingModel()), "numpy", True
        )


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


def test_grep_tool_matches_paragraphs_case_insensitively_with_their_section():
    grep = rag.grep_tool(["Chapter 1\nVecna rose.\nWe ran.", "Chapter 2\nThe lich vecna fell."])
    assert grep("vecna") == "Chapter 1: Vecna rose.\n\nChapter 2: The lich vecna fell."
    assert grep("^We") == "Chapter 1: We ran."  # a pattern sees one paragraph, not the title
    assert "No paragraph matches" in grep("Tiamat")
    assert "Not a valid regular expression" in grep("(")


def test_grep_tool_shows_only_the_text_around_the_match():
    line = "x" * 300 + "Vecna" + "y" * 300
    found = rag.grep_tool(["Ch\n" + line])("vecna").removeprefix("Ch: ")
    assert found == "..." + "x" * rag.CONTEXT_CHARS + "Vecna" + "y" * rag.CONTEXT_CHARS + "..."


def test_grep_tool_caps_long_results():
    lines = rag.grep_tool(["Ch\n" + "\n".join(["a"] * (rag.MAX_MATCHES + 2))])("a").split("\n\n")
    assert len(lines) == rag.MAX_MATCHES + 1 and lines[-1] == "... and 2 more"


def test_agentic_agent_with_grep_can_call_it(capsys):
    model = TestModel(call_tools=["grep_campaign"])  # it greps for "a"
    output, _ = rag.agentic(fake_index(), model, grep=True).run("Where is the swamp?")
    assert output
    assert "grep_campaign('a') -> 1 paragraphs" in capsys.readouterr().out


def test_score_counts_a_hit_when_a_result_is_in_an_expected_section():
    questions = [
        {"kind": "name", "question": "Q1", "pattern": "swamp", "sections": ["Chapter 1:"]},
        {"kind": "name", "question": "Q2", "pattern": "nothing", "sections": ["Chapter 2:"]},
    ]
    missed, words, _ = evaluate.score(questions, evaluate.by_grep(fake_index().chunks))
    assert [q["question"] for q in missed] == ["Q2"]
    assert words == 9 / 2  # "Chapter 1: A temple: The swamp smelled of decay." for Q1 only
    missed, _, _ = evaluate.score(questions, evaluate.by_index(fake_index()))
    assert [q["question"] for q in missed] == ["Q2"]


NERWEN = Relation(
    source="Nerwen", relation="banished", target="Old Gods", quote="Nerwen banished the Old Gods."
)
CHUNKS = [
    "History\nNerwen banished the Old Gods.",
    "Chapter 1\nWe walked.",
    "Chapter 2\nIt’s said: Nerwen banished the Old Gods.",
]


def test_extractor_returns_relations():
    model = TestModel(custom_output_args=[NERWEN.model_dump()])
    assert graph.extract(graph.extractor(model), CHUNKS[0]) == [NERWEN]


def test_stated_needs_the_quote_and_both_names_in_the_chunk():
    def changed(**fields):
        return NERWEN.model_copy(update=fields)

    assert graph.stated(NERWEN, CHUNKS[0])
    assert graph.stated(changed(quote="NERWEN banished ... Old Gods"), CHUNKS[0])  # shortened
    assert graph.stated(changed(quote="It's said: Nerwen banished"), CHUNKS[2])  # straight quote
    assert not graph.stated(changed(quote="Nerwen destroyed the Old Gods."), CHUNKS[0])
    assert not graph.stated(changed(quote=""), CHUNKS[0])
    assert not graph.stated(changed(target="Old Gods of Chaos"), CHUNKS[0])
    assert not graph.stated(changed(target="old gods"), CHUNKS[0])  # no capital: not a name
    assert not graph.stated(changed(source="the narrator"), CHUNKS[0])  # no "I" in this text
    assert graph.stated(changed(source="the narrator"), CHUNKS[0] + " I saw it.")


def test_load_graph_extracts_once_then_reuses_the_cache(tmp_path, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(graph, "extract", lambda agent, chunk: calls.append(chunk) or [NERWEN])
    agent = graph.extractor(TestModel())
    first = load_graph(CHUNKS, tmp_path / "c.docx", agent)
    # Chapter 1 does not contain the quote, so its relation is left out.
    assert "Extracted 2 relations from 3 chunks (0 chunks skipped, 1 rel" in capsys.readouterr().out
    assert first.relations[0] == {**NERWEN.model_dump(), "section": "History"}
    assert (tmp_path / "c.aliases.json").exists()  # the names were grouped once, too
    second = load_graph(CHUNKS, tmp_path / "c.docx", agent)
    assert capsys.readouterr().out == ""
    assert second.relations == first.relations and len(calls) == 3
    load_graph([*CHUNKS, "Chapter 3\nNew."], tmp_path / "c.docx", agent)  # the text changed
    assert len(calls) == 7


def test_load_graph_continues_after_an_interruption_and_skips_unusable_output(
    tmp_path, monkeypatch, capsys
):
    def stops_at_the_second_chunk(agent, chunk):
        if chunk == CHUNKS[1]:
            raise KeyboardInterrupt
        return [NERWEN]

    def second_chunk_is_unusable(agent, chunk):
        seen.append(chunk)
        if chunk == CHUNKS[1]:
            raise UnexpectedModelBehavior("not json")
        return [NERWEN]

    agent, seen = graph.extractor(TestModel()), []
    monkeypatch.setattr(graph, "extract", stops_at_the_second_chunk)
    with pytest.raises(KeyboardInterrupt):
        load_graph(CHUNKS, tmp_path / "c.docx", agent)
    monkeypatch.setattr(graph, "extract", second_chunk_is_unusable)
    resumed = load_graph(CHUNKS, tmp_path / "c.docx", agent)
    assert seen == CHUNKS[1:]  # the first chunk was not read again
    assert [row["section"] for row in resumed.relations] == ["History", "Chapter 2"]
    assert "(1 chunks skipped, 0 relations dropped" in capsys.readouterr().out


def test_graph_finds_a_name_at_either_end_once():
    rows = [
        {
            "source": "Kallista",
            "relation": "is the capital of",
            "target": "Carverun",
            "section": "A",
        },
        {
            "source": "kallista",
            "relation": "is the capital of",
            "target": "Carverun",
            "section": "B",
        },
        {"source": "The Sable Enclave", "relation": "is in", "target": "Kallista", "section": "C"},
        {"source": "Nerwen", "relation": "nurtured", "target": "Ancora", "section": "D"},
    ]
    assert [row["section"] for row in Graph(rows).about(" KALLISTA ")] == ["A", "C"]


def test_aliases_are_drafted_once_and_an_edited_file_is_kept(tmp_path, capsys):
    rows = [{**NERWEN.model_dump(), "source": "Cevan", "target": "Vecna", "section": "A"}]
    model = TestModel(custom_output_args={"groups": [["Vecna", "Cevan", "Nobody"], ["Cevan"]]})
    path = tmp_path / "c.aliases.json"
    # "Nobody" is not a name in the graph, and a group of one says nothing.
    assert graph.load_aliases(path, rows, model) == [["Vecna", "Cevan"]]
    assert "Review that file" in capsys.readouterr().out
    path.write_text('[["Cevan", "Vecna", "Rayl"]]')
    assert graph.load_aliases(path, rows, model) == [["Cevan", "Vecna", "Rayl"]]


def test_graph_follows_aliases_and_the_tool_names_them():
    rows = [
        {**NERWEN.model_dump(), "source": "Lord Cevan", "section": "A"},
        {**NERWEN.model_dump(), "source": "Vecna the Undying", "section": "B"},
        {**NERWEN.model_dump(), "section": "C"},
    ]
    assert [row["section"] for row in Graph(rows).about("cevan")] == ["A"]
    merged = Graph(rows, [["Vecna", "Cevan"]])
    assert [row["section"] for row in merged.about("cevan")] == ["A", "B"]
    assert rag.relations_tool(merged)("Cevan").startswith("These names are the same: Vecna, Cevan.")
    assert "These names" not in rag.relations_tool(merged)("Nerwen")


def test_agentic_agent_with_a_graph_can_look_up_relations(capsys):
    rows = [{**NERWEN.model_dump(), "target": "Ancora", "section": "History"}]
    model = TestModel(call_tools=["campaign_relations"])  # it looks up the name "a"
    output, _ = rag.agentic(fake_index(), model, Graph(rows)).run("Who is Nerwen?")
    assert output
    assert "campaign_relations('a') -> 1 relations" in capsys.readouterr().out


def test_relations_tool_caps_long_results_and_says_when_nothing_is_found():
    rows = [
        {**NERWEN.model_dump(), "relation": f"knows {n}", "section": "History"}
        for n in range(rag.MAX_RELATIONS + 2)
    ]
    lookup = rag.relations_tool(Graph(rows))
    lines = lookup("Nerwen").splitlines()
    assert lines[0] == 'Nerwen | knows 0 | Old Gods (History): "Nerwen banished the Old Gods."'
    assert len(lines) == rag.MAX_RELATIONS + 1 and lines[-1] == "... and 2 more"
    assert "Nothing in the graph" in lookup("Vecna")
