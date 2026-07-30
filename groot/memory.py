"""Local, file-based memory for Groot, backed by Chroma.

Embeddings are computed via Ollama (localhost only) rather than Chroma's default
embedding function, which would silently download a model from HuggingFace on first
use — that breaks the offline-by-default rule. Everything here stays on the same
already-approved localhost:11434 channel.

The Chroma store lives under memory/chroma/ so the whole memory/ folder can be
copied wholesale to a new machine later (Phase 7).
"""

from __future__ import annotations

import uuid

import chromadb
import requests
from chromadb.api.types import Documents, EmbeddingFunction

from groot.config import MEMORY_DIR, Config

COLLECTION_NAME = "groot_memory"


class OllamaEmbeddingFunction(EmbeddingFunction[Documents]):
    """Chroma embedding function that calls Ollama's /api/embed endpoint.

    Inherits from chromadb's EmbeddingFunction protocol class (not just structurally
    matching it) to pick up its default embed_query/embed_documents implementations.
    """

    def __init__(self, config: Config):
        self.model = config.embedding_model
        self.base_url = config.ollama_host.rstrip("/")

    def __call__(self, input: list[str]) -> list[list[float]]:
        resp = requests.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": input},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]

    def name(self) -> str:
        return "ollama-" + self.model


class MemoryStore:
    def __init__(self, config: Config):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(MEMORY_DIR))
        self.collection = self.client.get_or_create_collection(
            COLLECTION_NAME, embedding_function=OllamaEmbeddingFunction(config)
        )

    def add(self, text: str, category: str) -> None:
        self.collection.add(
            documents=[text],
            ids=[str(uuid.uuid4())],
            metadatas=[{"category": category}],
        )

    def query(self, text: str, n_results: int = 3) -> list[str]:
        if self.collection.count() == 0:
            return []
        results = self.collection.query(
            query_texts=[text], n_results=min(n_results, self.collection.count())
        )
        return results["documents"][0]
