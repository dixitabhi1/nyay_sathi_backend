from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np

from app.core.config import Settings


class FaissVectorStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.index_path: Path = settings.vector_index_path
        self.metadata_path: Path = settings.vector_metadata_path
        self.index: faiss.Index | None = None
        self.metadata: list[dict] = []

    def exists(self) -> bool:
        return self.index_path.exists() and self.metadata_path.exists()

    def build(self, embeddings: np.ndarray, metadata: list[dict]) -> None:
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)
        index.add(embeddings)
        faiss.write_index(index, str(self.index_path))
        self.metadata_path.write_text(json.dumps(metadata, ensure_ascii=True, separators=(",", ":")), encoding="utf-8")
        self.index = index
        self.metadata = metadata

    def load(self) -> None:
        if self.index is None:
            self.index = faiss.read_index(str(self.index_path))
            with self.metadata_path.open("r", encoding="utf-8") as handle:
                self.metadata = json.load(handle)

    def search(self, query_vector: np.ndarray, top_k: int) -> list[dict]:
        self.load()
        scores, indices = self.index.search(query_vector, top_k)
        matches: list[dict] = []
        for score, idx in zip(scores[0], indices[0], strict=False):
            if idx < 0 or idx >= len(self.metadata):
                continue
            item = dict(self.metadata[idx])
            item["score"] = float(score)
            matches.append(item)
        return matches
