from __future__ import annotations

from typing import Iterable

import numpy as np

from app.core.config import Settings

LEGAL_SCOPE_ANCHORS = [
    "Indian legal question about FIR registration, police complaint, criminal law, BNS, IPC, BNSS, BSA, arrest, bail, evidence, and investigation.",
    "Indian civil or commercial legal question about contracts, legal notices, tenant rights, consumer protection, property disputes, compensation, and legal remedies.",
    "Legal research request about statutes, bare acts, court judgments, legal drafting, legal procedure, rights, and compliance under Indian law.",
]

NON_LEGAL_SCOPE_ANCHORS = [
    "Personal memory question about my name, age, identity, preferences, biography, or conversation memory.",
    "General trivia or casual conversation unrelated to law, courts, police procedure, legal rights, contracts, statutes, or judgments.",
    "Non-legal request about entertainment, sports, weather, travel, recipes, coding help, or everyday chit-chat.",
]


def build_embedding_text(record: dict) -> str:
    parts = [
        record.get("title", ""),
        record.get("citation", ""),
        record.get("summary", ""),
        record.get("text", ""),
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
        return self.encode([text])

    def max_similarity(self, query_vector: np.ndarray, candidate_vectors: np.ndarray) -> float:
        if candidate_vectors.size == 0:
            return 0.0
        similarities = candidate_vectors @ query_vector[0]
        return float(np.max(similarities))
