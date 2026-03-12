from __future__ import annotations

import json
from pathlib import Path
import re

from app.core.config import Settings
from app.services.embeddings import EmbeddingService, build_embedding_text
from app.services.vector_store import FaissVectorStore

EXPLICIT_NON_LEGAL_PATTERNS = [
    re.compile(r"\bweather\b", re.IGNORECASE),
    re.compile(r"\bjoke\b", re.IGNORECASE),
    re.compile(r"\bpoem\b", re.IGNORECASE),
    re.compile(r"\brecipe\b", re.IGNORECASE),
    re.compile(r"\bcricket\b", re.IGNORECASE),
    re.compile(r"\breact hooks?\b", re.IGNORECASE),
    re.compile(r"\bmy name\b", re.IGNORECASE),
    re.compile(r"\bdata structures?\b", re.IGNORECASE),
    re.compile(r"\balgorithms?\b", re.IGNORECASE),
    re.compile(r"\bprogramming\b", re.IGNORECASE),
    re.compile(r"\bcoding\b", re.IGNORECASE),
    re.compile(r"\bpython\b", re.IGNORECASE),
    re.compile(r"\bjava(script)?\b", re.IGNORECASE),
    re.compile(r"\bc\+\+\b", re.IGNORECASE),
    re.compile(r"\bdbms\b", re.IGNORECASE),
    re.compile(r"\boperating system\b", re.IGNORECASE),
    re.compile(r"\bmachine learning\b", re.IGNORECASE),
    re.compile(r"\bdeep learning\b", re.IGNORECASE),
]

LEGAL_INTENT_PATTERNS = [
    re.compile(r"\b(section|sections|act|law|legal|fir|complaint|bns|bnss|bsa|ipc)\b", re.IGNORECASE),
    re.compile(r"\b(arrest|bail|evidence|contract|notice|rights|judgment|court|police)\b", re.IGNORECASE),
    re.compile(r"\b(theft|cheating|fraud|threat|intimidation|assault|harassment|trespass)\b", re.IGNORECASE),
    re.compile(r"\b(defamation|extortion|murder|kidnapping|dowry|stalking|cybercrime|cyber crime)\b", re.IGNORECASE),
    re.compile(r"\b(tenant|landlord|property|consumer|copyright|trademark|divorce|maintenance|succession|will)\b", re.IGNORECASE),
]

LEGAL_REFERENCE_PATTERNS = [
    re.compile(r"\b(section|act|code|sanhita|adhiniyam|judgment|court|rights|procedure|fir)\b", re.IGNORECASE),
    re.compile(r"\b(bns|bnss|bsa|ipc|crpc|contract act|evidence act|consumer protection)\b", re.IGNORECASE),
]

OFFICIAL_SOURCE_HOSTS = (
    "indiacode.nic.in",
    "legislative.gov.in",
    "sci.gov.in",
    "ecourts.gov.in",
)

SUBSTANTIVE_OFFENCE_KEYWORDS = (
    "defamation",
    "theft",
    "cheating",
    "fraud",
    "extortion",
    "murder",
    "kidnapping",
    "stalking",
    "harassment",
    "intimidation",
    "trespass",
)


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
        explicit_override = self._explicit_scope_override(query)
        if explicit_override is not None:
            return explicit_override

        has_legal_intent = self._has_legal_intent(query)
        exact_hits = self.lookup_exact_reference(query, self.settings.top_k_retrieval)
        if exact_hits:
            top_corpus_score = exact_hits[0]["score"] if exact_hits else 0.0
            return {
                "in_scope": True,
                "hits": exact_hits,
                "has_legal_intent": True,
                "grounded_hit_count": len(exact_hits),
                "legal_anchor_score": 1.0,
                "non_legal_anchor_score": 0.0,
                "anchor_margin": 1.0,
                "top_corpus_score": round(top_corpus_score, 4),
            }

        query_vector = self.embeddings.encode_query(query)
        raw_hits = self.search_by_vector(query_vector, max(self.settings.top_k_retrieval * 4, 12))
        hits = self._rerank_hits(query, raw_hits, self.settings.top_k_retrieval)
        grounded_hits = self._filter_grounded_hits(hits)
        top_corpus_score = grounded_hits[0]["score"] if grounded_hits else 0.0
        legal_anchor_score = self.embeddings.max_similarity(query_vector, self.embeddings.legal_scope_anchor_embeddings)
        non_legal_anchor_score = self.embeddings.max_similarity(query_vector, self.embeddings.non_legal_scope_anchor_embeddings)
        anchor_margin = legal_anchor_score - non_legal_anchor_score
        semantic_legal_match = (
            legal_anchor_score >= self.settings.legal_scope_anchor_threshold
            and anchor_margin >= self.settings.legal_scope_margin
        )
        in_scope = has_legal_intent and bool(grounded_hits) and (
            semantic_legal_match or top_corpus_score >= self.settings.legal_scope_corpus_threshold
        )
        return {
            "in_scope": in_scope,
            "hits": grounded_hits if in_scope else [],
            "has_legal_intent": has_legal_intent,
            "grounded_hit_count": len(grounded_hits),
            "legal_anchor_score": round(legal_anchor_score, 4),
            "non_legal_anchor_score": round(non_legal_anchor_score, 4),
            "anchor_margin": round(anchor_margin, 4),
            "top_corpus_score": round(top_corpus_score, 4),
        }

    def _warmup_embeddings(self) -> None:
        _ = self.embeddings.legal_scope_anchor_embeddings

    def _explicit_scope_override(self, query: str) -> dict | None:
        normalized = query.strip().lower()
        has_legal_intent = self._has_legal_intent(normalized)
        matched_non_legal = [pattern.pattern for pattern in EXPLICIT_NON_LEGAL_PATTERNS if pattern.search(normalized)]

        if matched_non_legal and not has_legal_intent:
            return {
                "in_scope": False,
                "hits": [],
                "has_legal_intent": False,
                "grounded_hit_count": 0,
                "legal_anchor_score": 0.0,
                "non_legal_anchor_score": 1.0,
                "anchor_margin": -1.0,
                "top_corpus_score": 0.0,
                "explicit_out_of_scope": True,
                "matched_non_legal_patterns": matched_non_legal,
            }
        return None

    def _has_legal_intent(self, query: str) -> bool:
        return any(pattern.search(query) for pattern in LEGAL_INTENT_PATTERNS)

    def _filter_grounded_hits(self, hits: list[dict]) -> list[dict]:
        return [item for item in hits if self._is_grounded_legal_hit(item)]

    def _is_grounded_legal_hit(self, item: dict) -> bool:
        source_type = str(item.get("source_type", "")).lower()
        source_url = str(item.get("source_url", "")).lower()
        haystack = f"{item.get('source_id', '')} {item.get('title', '')} {item.get('citation', '')} {item.get('text', '')}".lower()
        has_legal_reference = any(pattern.search(haystack) for pattern in LEGAL_REFERENCE_PATTERNS)
        from_official_host = any(host in source_url for host in OFFICIAL_SOURCE_HOSTS)
        from_legal_source_type = source_type in {"statute", "judgment", "case_law", "precedent"}
        return from_official_host or (from_legal_source_type and has_legal_reference)

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
            return (
                source_id == "bnss"
                or source_id.startswith("bnss_")
                or bool(re.search(r"\bbnss\b", haystack))
                or "bharatiya nagarik suraksha sanhita" in haystack
            )
        if statute == "bns":
            return (
                source_id == "bns"
                or source_id.startswith("bns_")
                or bool(re.search(r"\bbns\b", haystack))
                or "bharatiya nyaya sanhita" in haystack
            )
        if statute == "bsa":
            return (
                source_id == "bsa"
                or source_id.startswith("bsa_")
                or bool(re.search(r"\bbsa\b", haystack))
                or "bharatiya sakshya adhiniyam" in haystack
            )
        if statute == "ipc":
            return (
                source_id == "ipc"
                or source_id.startswith("ipc_")
                or bool(re.search(r"\bipc\b", haystack))
                or "indian penal code" in haystack
            )
        return False

    def _rerank_hits(self, query: str, hits: list[dict], top_k: int) -> list[dict]:
        normalized = query.lower()
        wants_bns = "bns" in normalized or "bharatiya nyaya sanhita" in normalized
        wants_bnss = "bnss" in normalized or "bharatiya nagarik suraksha sanhita" in normalized
        wants_ipc_compare = "ipc" in normalized or "compare" in normalized or "comparison" in normalized
        wants_substantive_offence = (
            any(keyword in normalized for keyword in SUBSTANTIVE_OFFENCE_KEYWORDS)
            and "procedure" not in normalized
            and "cognizable" not in normalized
            and "bailable" not in normalized
        )

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
            if wants_substantive_offence:
                if "bns" in haystack or "bharatiya nyaya sanhita" in haystack:
                    adjusted += 0.16
                if "bnss" in haystack or "bharatiya nagarik suraksha sanhita" in haystack:
                    adjusted -= 0.18
                if "cognizable" in haystack and "bailable" in haystack:
                    adjusted -= 0.12
                if re.search(r"\|\s*section\s+531", item.get("citation", ""), flags=re.IGNORECASE):
                    adjusted -= 0.25

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
