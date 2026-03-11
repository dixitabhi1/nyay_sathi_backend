from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings
from app.services.embeddings import EmbeddingService, build_embedding_text
from app.services.vector_store import FaissVectorStore


class Retriever:
    def __init__(self, settings: Settings, embeddings: EmbeddingService, vector_store: FaissVectorStore) -> None:
        self.settings = settings
        self.embeddings = embeddings
        self.vector_store = vector_store

    def ensure_index(self) -> None:
        if self.vector_store.exists():
            self._warmup_embeddings()
            return

        corpus_path = Path(self.settings.legal_corpus_path)
        if not corpus_path.exists():
            corpus_path = Path(self.settings.bootstrap_corpus_path)
        documents = [
            json.loads(line)
            for line in corpus_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        embeddings = self.embeddings.encode(build_embedding_text(doc) for doc in documents)
        self.vector_store.build(embeddings, documents)
        self._warmup_embeddings()

    def search(self, query: str, top_k: int | None = None) -> list[dict]:
        query_vector = self.embeddings.encode_query(query)
        return self.search_by_vector(query_vector, top_k or self.settings.top_k_retrieval)

    def search_by_vector(self, query_vector, top_k: int) -> list[dict]:
        return self.vector_store.search(query_vector, top_k)

    def assess_scope(self, query: str) -> dict:
        query_vector = self.embeddings.encode_query(query)
        hits = self.search_by_vector(query_vector, self.settings.top_k_retrieval)
        top_corpus_score = hits[0]["score"] if hits else 0.0
        legal_anchor_score = self.embeddings.max_similarity(query_vector, self.embeddings.legal_scope_anchor_embeddings)
        non_legal_anchor_score = self.embeddings.max_similarity(query_vector, self.embeddings.non_legal_scope_anchor_embeddings)
        anchor_margin = legal_anchor_score - non_legal_anchor_score
        in_scope = (
            legal_anchor_score >= self.settings.legal_scope_anchor_threshold
            and anchor_margin >= self.settings.legal_scope_margin
        ) or top_corpus_score >= self.settings.legal_scope_corpus_threshold
        return {
            "in_scope": in_scope,
            "hits": hits,
            "legal_anchor_score": round(legal_anchor_score, 4),
            "non_legal_anchor_score": round(non_legal_anchor_score, 4),
            "anchor_margin": round(anchor_margin, 4),
            "top_corpus_score": round(top_corpus_score, 4),
        }

    def _warmup_embeddings(self) -> None:
        _ = self.embeddings.legal_scope_anchor_embeddings
