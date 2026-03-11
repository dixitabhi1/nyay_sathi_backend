from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


class LegalRAGPipeline:
    def __init__(
        self,
        embedding_model_name: str = "BAAI/bge-m3",
        index_path: str = "data/index/legal.index",
        metadata_path: str = "data/index/legal_metadata.json",
    ) -> None:
        self.model = SentenceTransformer(embedding_model_name)
        self.index = faiss.read_index(index_path)
        self.metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))

    def search(self, query: str, top_k: int = 4) -> list[dict]:
        vector = self.model.encode([query], normalize_embeddings=True)
        scores, indices = self.index.search(np.asarray(vector, dtype="float32"), top_k)
        results: list[dict] = []
        for score, idx in zip(scores[0], indices[0], strict=False):
            if idx < 0:
                continue
            item = dict(self.metadata[idx])
            item["score"] = float(score)
            results.append(item)
        return results

    def format_context(self, query: str, top_k: int = 4) -> str:
        results = self.search(query, top_k=top_k)
        return "\n\n".join(
            f"{row['title']} ({row['citation']})\nSummary: {row.get('summary', '')}\n{row['text']}"
            for row in results
        )
