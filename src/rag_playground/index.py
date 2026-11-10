"""Embed the chunks once, keep them on disk, and search them by cosine similarity.

The vectors are cached in an .npz file. Search runs in a LanceDB table built from that file,
or directly in numpy with RAG_STORE=numpy. Both return the same chunks.
"""

import os
from pathlib import Path

import lancedb
import numpy as np
from pydantic_ai import Embedder
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.providers.ollama import OllamaProvider

from rag_playground import loader

DEFAULT_DOC = "data/rag/setting-the-darkness-ablaze.docx"
DEFAULT_EMBED_MODEL = "bge-m3"
OLLAMA_BASE_URL = "http://localhost:11434/v1"
BATCH = 32
STORES = ("lancedb", "numpy")


def ollama() -> OllamaProvider:
    return OllamaProvider(base_url=os.getenv("OLLAMA_BASE_URL") or OLLAMA_BASE_URL)


def default_embedder() -> Embedder:
    name = os.getenv("RAG_EMBED_MODEL") or DEFAULT_EMBED_MODEL
    return Embedder(OpenAIEmbeddingModel(name, provider=ollama()))


def _unit(vectors) -> np.ndarray:
    array = np.asarray(vectors, dtype=np.float32)
    return array / np.linalg.norm(array, axis=-1, keepdims=True)


def top_k(vectors: np.ndarray, query: np.ndarray, k: int) -> list[int]:
    """Row numbers of the `k` vectors closest to `query`. Both must be unit length."""
    return np.argsort(vectors @ query)[::-1][:k].tolist()


def lance_table(path: str | Path, chunks: list[str], vectors: np.ndarray):
    """A LanceDB table holding every chunk with its vector and section title."""
    db = lancedb.connect(path)
    # shortcut: rebuilt from the .npz on every start (15 ms at 657 rows) so it can never be
    # stale; switch to adding only new rows when the corpus gets big.
    db.drop_all_tables()  # this folder holds nothing else
    rows = [
        {"vector": vector, "text": chunk, "section": chunk.partition("\n")[0]}
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    return db.create_table("chunks", data=rows)


class Index:
    def __init__(self, chunks: list[str], vectors: np.ndarray, embedder: Embedder, table=None):
        """Searches `table` (LanceDB) when given, otherwise the vectors in numpy."""
        self.chunks, self.vectors, self.embedder, self.table = chunks, vectors, embedder, table

    @property
    def store(self) -> str:
        return "numpy" if self.table is None else "lancedb"

    def search(self, query: str, k: int = 5) -> list[str]:
        vector = _unit(self.embedder.embed_query_sync(query).embeddings[0])
        if self.table is None:
            return [self.chunks[i] for i in top_k(self.vectors, vector, k)]
        rows = self.table.search(vector).distance_type("cosine").limit(k).to_list()
        return [row["text"] for row in rows]


def load_index(
    doc: str | Path | None = None, embedder: Embedder | None = None, store: str | None = None
) -> Index:
    """The index for `doc`, embedded on first use and reused until the file or model changes."""
    store = store or os.getenv("RAG_STORE") or STORES[0]
    if store not in STORES:
        raise ValueError(f"RAG_STORE must be one of {STORES}, not {store!r}")
    doc = Path(doc or os.getenv("RAG_DOC") or DEFAULT_DOC)
    embedder = embedder or default_embedder()
    stat = doc.stat()
    name = getattr(embedder.model, "model_name", embedder.model)  # model may be a plain string
    key = f"{name}:{stat.st_mtime_ns}:{stat.st_size}:{loader.CHUNK_WORDS}"
    cache = doc.with_suffix(".index.npz")
    if cache.exists():
        saved = np.load(cache)
        if str(saved["key"]) == key:
            return _index(doc, saved["chunks"].tolist(), saved["vectors"], embedder, store)

    chunks = loader.chunks(doc)
    if not chunks:
        raise ValueError(f"No text found under a heading in {doc}")
    vectors = []
    for start in range(0, len(chunks), BATCH):
        print(f"\rEmbedding {start}/{len(chunks)} chunks...", end="", flush=True)
        vectors.extend(embedder.embed_documents_sync(chunks[start : start + BATCH]).embeddings)
    print(f"\rEmbedded {len(chunks)} chunks.        ")
    unit = _unit(vectors)
    np.savez(cache, key=key, chunks=np.array(chunks), vectors=unit)
    return _index(doc, chunks, unit, embedder, store)


def _index(doc: Path, chunks: list[str], vectors: np.ndarray, embedder: Embedder, store: str):
    table = (
        lance_table(doc.with_suffix(".lancedb"), chunks, vectors) if store == "lancedb" else None
    )
    return Index(chunks, vectors, embedder, table)
