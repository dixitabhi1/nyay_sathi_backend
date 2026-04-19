from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

import numpy as np

from app.core.config import Settings

LEGAL_SCOPE_ANCHORS = [
    "Indian legal question about FIR registration, police complaint, criminal law, BNS, IPC, BNSS, CrPC, BSA, arrest, bail, evidence, and investigation.",
    "Indian civil or commercial legal question about contracts, legal notices, tenant rights, consumer protection, property disputes, compensation, and legal remedies.",
    "Legal research request about statutes, bare acts, court judgments, legal drafting, legal procedure, rights, compliance, privacy, and data protection under Indian law including the DPDP Act 2023.",
]

NON_LEGAL_SCOPE_ANCHORS = [
    "Personal memory question about my name, age, identity, preferences, biography, or conversation memory.",
    "General trivia or casual conversation unrelated to law, courts, police procedure, legal rights, contracts, statutes, or judgments.",
    "Non-legal request about entertainment, sports, weather, travel, recipes, coding help, or everyday chit-chat.",
]


def build_embedding_text(record: dict) -> str:
    parts = [
        record.get("source_id", ""),
        record.get("document_type", ""),
        record.get("chunk_strategy", ""),
        record.get("title", ""),
        record.get("citation", ""),
        record.get("summary", ""),
        record.get("text", ""),
        " ".join(record.get("linked_citations", [])) if isinstance(record.get("linked_citations"), list) else "",
        record.get("question", ""),
        record.get("context", ""),
        record.get("answer", ""),
    ]
    return "\n".join(part.strip() for part in parts if isinstance(part, str) and part.strip())


class EmbeddingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = None
        self._legal_scope_anchor_embeddings = None
        self._non_legal_scope_anchor_embeddings = None
        self._query_cache: OrderedDict[str, np.ndarray] = OrderedDict()

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.settings.embedding_model_name, device="cpu")
        return self._model

    @property
    def legal_scope_anchor_embeddings(self) -> np.ndarray:
        if self._legal_scope_anchor_embeddings is None:
            self._legal_scope_anchor_embeddings = self.encode(LEGAL_SCOPE_ANCHORS)
        return self._legal_scope_anchor_embeddings

    @property
    def non_legal_scope_anchor_embeddings(self) -> np.ndarray:
        if self._non_legal_scope_anchor_embeddings is None:
            self._non_legal_scope_anchor_embeddings = self.encode(NON_LEGAL_SCOPE_ANCHORS)
        return self._non_legal_scope_anchor_embeddings

    def encode(self, texts: Iterable[str]) -> np.ndarray:
        embeddings = self.model.encode(list(texts), normalize_embeddings=True)
        return np.asarray(embeddings, dtype="float32")

    def encode_query(self, text: str) -> np.ndarray:
        normalized = " ".join(text.strip().split())
        cached = self._query_cache.get(normalized)
        if cached is not None:
            self._query_cache.move_to_end(normalized)
            return cached
        embedding = self.encode([normalized])
        self._query_cache[normalized] = embedding
        max_items = max(16, int(self.settings.query_embedding_cache_size))
        while len(self._query_cache) > max_items:
            self._query_cache.popitem(last=False)
        return embedding

    def max_similarity(self, query_vector: np.ndarray, candidate_vectors: np.ndarray) -> float:
        if candidate_vectors.size == 0:
            return 0.0
        similarities = candidate_vectors @ query_vector[0]
        return float(np.max(similarities))
