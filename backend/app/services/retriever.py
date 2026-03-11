from __future__ import annotations

import json
from pathlib import Path
import re

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
        requested_top_k = top_k or self.settings.top_k_retrieval
        exact_hits = self.lookup_exact_reference(query, requested_top_k)
        if exact_hits:
            return exact_hits

        query_vector = self.embeddings.encode_query(query)
        candidate_top_k = max(requested_top_k * 4, 12)
        raw_hits = self.search_by_vector(query_vector, candidate_top_k)
        return self._rerank_hits(query, raw_hits, requested_top_k)

    def search_by_vector(self, query_vector, top_k: int) -> list[dict]:
        return self.vector_store.search(query_vector, top_k)

    def assess_scope(self, query: str) -> dict:
        exact_hits = self.lookup_exact_reference(query, self.settings.top_k_retrieval)
        if exact_hits:
            top_corpus_score = exact_hits[0]["score"] if exact_hits else 0.0
            return {
                "in_scope": True,
                "hits": exact_hits,
                "legal_anchor_score": 1.0,
                "non_legal_anchor_score": 0.0,
                "anchor_margin": 1.0,
                "top_corpus_score": round(top_corpus_score, 4),
            }

        query_vector = self.embeddings.encode_query(query)
        raw_hits = self.search_by_vector(query_vector, max(self.settings.top_k_retrieval * 4, 12))
        hits = self._rerank_hits(query, raw_hits, self.settings.top_k_retrieval)
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

    def lookup_exact_reference(self, query: str, top_k: int) -> list[dict]:
        normalized = query.lower()
        statute = self._detect_statute(normalized)
        if not statute:
            return []

        section_match = re.search(r"\bsection\s+(\d+[a-zA-Z-]*)(?:\((\d+[a-zA-Z]?)\))?", normalized)
        if not section_match:
            return []

        section_number = section_match.group(1)
        subsection = section_match.group(2)

        self.vector_store.load()
        ranked: list[dict] = []
        for item in self.vector_store.metadata:
            if not self._matches_statute(item, statute):
                continue

            citation = item.get("citation", "")
            exact_subsection_pattern = rf"\|\s*section\s+{re.escape(section_number)}\({re.escape(subsection or '')}\)\b"
            exact_section_pattern = rf"\|\s*section\s+{re.escape(section_number)}\b"

            bonus = 0.0
            if subsection and re.search(exact_subsection_pattern, citation, flags=re.IGNORECASE):
                bonus = 1.0
            elif re.search(exact_section_pattern, citation, flags=re.IGNORECASE):
                bonus = 0.9
            else:
                continue

            exact_item = dict(item)
            exact_item["score"] = bonus
            ranked.append(exact_item)

        ranked.sort(key=lambda row: (row["score"], len(row.get("text", ""))), reverse=True)
        return ranked[:top_k]

    def _detect_statute(self, normalized_query: str) -> str | None:
        if re.search(r"\bbnss\b", normalized_query) or "bharatiya nagarik suraksha sanhita" in normalized_query:
            return "bnss"
        if re.search(r"\bbns\b", normalized_query) or "bharatiya nyaya sanhita" in normalized_query:
            return "bns"
        if re.search(r"\bbsa\b", normalized_query) or "bharatiya sakshya adhiniyam" in normalized_query:
            return "bsa"
        if re.search(r"\bipc\b", normalized_query) or "indian penal code" in normalized_query:
            return "ipc"
        return None

    def _matches_statute(self, item: dict, statute: str) -> bool:
        source_id = str(item.get("source_id", "")).lower()
        haystack = f"{source_id} {item.get('title', '')} {item.get('citation', '')}".lower()
        if statute == "bnss":
            return source_id.startswith("bnss") or bool(re.search(r"\bbnss\b", haystack)) or "bharatiya nagarik suraksha sanhita" in haystack
        if statute == "bns":
            return source_id.startswith("bns") or bool(re.search(r"\bbns\b", haystack)) or "bharatiya nyaya sanhita" in haystack
        if statute == "bsa":
            return source_id.startswith("bsa") or bool(re.search(r"\bbsa\b", haystack)) or "bharatiya sakshya adhiniyam" in haystack
        if statute == "ipc":
            return source_id.startswith("ipc") or bool(re.search(r"\bipc\b", haystack)) or "indian penal code" in haystack
        return False

    def _rerank_hits(self, query: str, hits: list[dict], top_k: int) -> list[dict]:
        normalized = query.lower()
        wants_bns = "bns" in normalized or "bharatiya nyaya sanhita" in normalized
        wants_bnss = "bnss" in normalized or "bharatiya nagarik suraksha sanhita" in normalized
        wants_ipc_compare = "ipc" in normalized or "compare" in normalized or "comparison" in normalized

        reranked: list[dict] = []
        for item in hits:
            haystack = f"{item.get('title', '')} {item.get('citation', '')} {item.get('text', '')}".lower()
            adjusted = float(item["score"])
            source_url = (item.get("source_url") or "").lower()

            if "indiacode.nic.in" in source_url or "legislative.gov.in" in source_url:
                adjusted += 0.08
            if wants_bns and ("bns" in haystack or "bharatiya nyaya sanhita" in haystack):
                adjusted += 0.22
            if wants_bnss and ("bnss" in haystack or "bharatiya nagarik suraksha sanhita" in haystack):
                adjusted += 0.22
            if (wants_bns or wants_bnss) and "ipc" in haystack and not wants_ipc_compare:
                adjusted -= 0.06
            if re.search(r"\|\s*section\s+\d+\(\d+[a-z]?\)", item.get("citation", ""), flags=re.IGNORECASE):
                adjusted += 0.04

            reranked_item = dict(item)
            reranked_item["score"] = round(adjusted, 6)
            reranked.append(reranked_item)

        reranked.sort(key=lambda row: row["score"], reverse=True)

        if wants_ipc_compare or wants_bns or wants_bnss:
            primary: list[dict] = []
            comparison: list[dict] = []
            for item in reranked:
                haystack = f"{item.get('title', '')} {item.get('citation', '')}".lower()
                if "ipc" in haystack:
                    comparison.append(item)
                else:
                    primary.append(item)

            merged = primary[: max(top_k - 1, 1)]
            if comparison and len(merged) < top_k:
                merged.append(comparison[0])
            if len(merged) < top_k:
                seen_ids = {id(row) for row in merged}
                merged.extend([row for row in reranked if id(row) not in seen_ids][: top_k - len(merged)])
            return merged[:top_k]

        return reranked[:top_k]
