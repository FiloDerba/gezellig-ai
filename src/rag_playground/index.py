"""Embed the chunks once, keep them on disk, and search them by cosine similarity."""

import os
from pathlib import Path

import numpy as np
from pydantic_ai import Embedder
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.providers.ollama import OllamaProvider

from rag_playground import loader

DEFAULT_DOC = "data/rag/setting-the-darkness-ablaze.docx"
DEFAULT_EMBED_MODEL = "bge-m3"
OLLAMA_BASE_URL = "http://localhost:11434/v1"
BATCH = 32


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


class Index:
    def __init__(self, chunks: list[str], vectors: np.ndarray, embedder: Embedder):
        self.chunks, self.vectors, self.embedder = chunks, vectors, embedder

    def search(self, query: str, k: int = 5) -> list[str]:
        vector = _unit(self.embedder.embed_query_sync(query).embeddings[0])
        return [self.chunks[i] for i in top_k(self.vectors, vector, k)]


def load_index(doc: str | Path | None = None, embedder: Embedder | None = None) -> Index:
    """The index for `doc`, embedded on first use and reused until the file or model changes."""
    doc = Path(doc or os.getenv("RAG_DOC") or DEFAULT_DOC)
    embedder = embedder or default_embedder()
    stat = doc.stat()
    name = getattr(embedder.model, "model_name", embedder.model)  # model may be a plain string
    key = f"{name}:{stat.st_mtime_ns}:{stat.st_size}:{loader.CHUNK_WORDS}"
    cache = doc.with_suffix(".index.npz")
    if cache.exists():
        saved = np.load(cache)
        if str(saved["key"]) == key:
            return Index(saved["chunks"].tolist(), saved["vectors"], embedder)

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
    return Index(chunks, unit, embedder)
