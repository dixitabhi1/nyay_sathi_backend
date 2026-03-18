from __future__ import annotations

import json
from pathlib import Path
import re

from app.core.config import Settings
from app.services.embeddings import EmbeddingService, build_embedding_text
from app.services.page_index import PageIndexStore
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
    def __init__(
        self,
        settings: Settings,
        embeddings: EmbeddingService,
        vector_store: FaissVectorStore,
        page_index: PageIndexStore,
    ) -> None:
        self.settings = settings
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.page_index = page_index

    def ensure_index(self) -> None:
        if self.vector_store.exists() and self.page_index.exists():
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
        if not self.vector_store.exists():
            embeddings = self.embeddings.encode(build_embedding_text(doc) for doc in documents)
            self.vector_store.build(embeddings, documents)
        if not self.page_index.exists():
            self.page_index.build(documents)
        self._warmup_embeddings()

    def search(self, query: str, top_k: int | None = None) -> list[dict]:
        requested_top_k = top_k or self.settings.top_k_retrieval
        query_parts = self._expand_query_parts(self._decompose_query(query))
        semantic_hits = self._search_semantic_queries(query_parts, requested_top_k)
        structural_hits = self._search_page_index_queries(query_parts, requested_top_k)
        fused_hits = self._fuse_hits(query, semantic_hits, structural_hits, requested_top_k)
        grounded_hits = self._filter_grounded_hits(fused_hits)
        return grounded_hits[:requested_top_k]

    def search_by_vector(self, query_vector, top_k: int) -> list[dict]:
        return self.vector_store.search(query_vector, top_k)

    def assess_scope(self, query: str) -> dict:
        explicit_override = self._explicit_scope_override(query)
        if explicit_override is not None:
            return explicit_override

        has_legal_intent = self._has_legal_intent(query)
        hits = self.search(query, self.settings.top_k_retrieval)
        grounded_hits = self._filter_grounded_hits(hits)
        top_corpus_score = grounded_hits[0]["score"] if grounded_hits else 0.0
        top_page_index_score = max((float(item.get("page_index_score", 0.0)) for item in grounded_hits), default=0.0)

        query_vector = self.embeddings.encode_query(query)
        legal_anchor_score = self.embeddings.max_similarity(query_vector, self.embeddings.legal_scope_anchor_embeddings)
        non_legal_anchor_score = self.embeddings.max_similarity(query_vector, self.embeddings.non_legal_scope_anchor_embeddings)
        anchor_margin = legal_anchor_score - non_legal_anchor_score
        semantic_legal_match = (
            legal_anchor_score >= self.settings.legal_scope_anchor_threshold
            and anchor_margin >= self.settings.legal_scope_margin
        )
        structural_legal_match = top_page_index_score >= self.settings.page_index_scope_threshold
        in_scope = has_legal_intent and bool(grounded_hits) and (
            semantic_legal_match
            or top_corpus_score >= self.settings.legal_scope_corpus_threshold
            or structural_legal_match
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
            "top_page_index_score": round(top_page_index_score, 4),
            "hybrid_confidence": round(top_corpus_score, 4),
        }

    def get_structure_overview(self, query: str) -> dict | None:
        return self.page_index.get_structure_overview(query)

    def _search_semantic_queries(self, query_parts: list[str], top_k: int) -> list[dict]:
        merged: dict[str, dict] = {}
        candidate_top_k = max(top_k * 4, 12)
        for query in query_parts:
            exact_hits = self._lookup_vector_exact_reference(query, max(top_k, 2))
            for hit in exact_hits:
                self._merge_hit(
                    merged,
                    hit,
                    semantic_score=1.0,
                    page_index_score=0.0,
                    retrieval_mode="semantic",
                )

            query_vector = self.embeddings.encode_query(query)
            raw_hits = self.search_by_vector(query_vector, candidate_top_k)
            reranked = self._rerank_hits(query, raw_hits, candidate_top_k)
            for hit in reranked:
                self._merge_hit(
                    merged,
                    hit,
                    semantic_score=self._normalize_semantic_score(hit.get("score", 0.0)),
                    page_index_score=0.0,
                    retrieval_mode="semantic",
                )
        return list(merged.values())

    def _search_page_index_queries(self, query_parts: list[str], top_k: int) -> list[dict]:
        merged: dict[str, dict] = {}
        candidate_top_k = max(top_k * 2, self.settings.page_index_top_k)
        for query in query_parts:
            for hit in self.page_index.search(query, candidate_top_k):
                self._merge_hit(
                    merged,
                    hit,
                    semantic_score=0.0,
                    page_index_score=hit.get("page_index_score", hit.get("score", 0.0)),
                    retrieval_mode="page_index",
                )
        return list(merged.values())

    def _merge_hit(
        self,
        merged: dict[str, dict],
        hit: dict,
        semantic_score: float,
        page_index_score: float,
        retrieval_mode: str,
    ) -> None:
        key = self._result_key(hit)
        current = merged.get(key)
        if current is None:
            current = dict(hit)
            current["semantic_score"] = 0.0
            current["page_index_score"] = 0.0
            current["retrieval_modes"] = []
            merged[key] = current

        current["semantic_score"] = max(float(current.get("semantic_score", 0.0)), float(semantic_score))
        current["page_index_score"] = max(float(current.get("page_index_score", 0.0)), float(page_index_score))
        current["retrieval_modes"] = sorted(set([*current.get("retrieval_modes", []), retrieval_mode]))

        for field in ("source_id", "title", "citation", "text", "summary", "source_type", "document_type", "source_url", "chunk_strategy"):
            if not current.get(field) and hit.get(field):
                current[field] = hit.get(field)
        if hit.get("reference_path"):
            current["reference_path"] = hit["reference_path"]
        if hit.get("linked_citations"):
            linked = current.get("linked_citations", [])
            for citation in hit["linked_citations"]:
                if citation not in linked:
                    linked.append(citation)
            current["linked_citations"] = linked

    def _fuse_hits(self, query: str, semantic_hits: list[dict], structural_hits: list[dict], top_k: int) -> list[dict]:
        merged: dict[str, dict] = {}
        for hit in semantic_hits:
            self._merge_hit(
                merged,
                hit,
                semantic_score=hit.get("semantic_score", 0.0),
                page_index_score=hit.get("page_index_score", 0.0),
                retrieval_mode="semantic",
            )
        for hit in structural_hits:
            self._merge_hit(
                merged,
                hit,
                semantic_score=hit.get("semantic_score", 0.0),
                page_index_score=hit.get("page_index_score", hit.get("score", 0.0)),
                retrieval_mode="page_index",
            )

        fused: list[dict] = []
        for item in merged.values():
            metadata_bonus = self._metadata_bonus(query, item)
            hybrid_score = (
                self.settings.hybrid_semantic_weight * float(item.get("semantic_score", 0.0))
                + self.settings.hybrid_page_index_weight * float(item.get("page_index_score", 0.0))
                + metadata_bonus
            )
            item["confidence"] = round(min(1.0, hybrid_score), 4)
            item["score"] = round(hybrid_score, 6)
            item["retrieval_mode"] = "+".join(item.get("retrieval_modes", [])) or "semantic"
            fused.append(item)

        reranked = self._rerank_hits(query, fused, max(top_k * 2, 8))
        return reranked[:top_k]

    def _metadata_bonus(self, query: str, item: dict) -> float:
        bonus = 0.0
        modes = set(item.get("retrieval_modes", []))
        if {"semantic", "page_index"}.issubset(modes):
            bonus += self.settings.hybrid_cross_signal_bonus
        source_url = str(item.get("source_url", "")).lower()
        if "indiacode.nic.in" in source_url or "legislative.gov.in" in source_url:
            bonus += 0.04
        citation = str(item.get("citation", ""))
        if re.search(r"\|\s*section\s+\d+(?:\([\da-zA-Z]+\))?", citation, flags=re.IGNORECASE):
            bonus += self.settings.hybrid_exact_reference_bonus
        if item.get("linked_citations"):
            bonus += min(0.03, len(item["linked_citations"]) * 0.01)
        act = self._detect_statute(query.lower())
        if act and self._matches_statute(item, act):
            bonus += 0.03
        return bonus

    def _normalize_semantic_score(self, score: float) -> float:
        return max(0.0, min(1.0, float(score)))

    def _result_key(self, item: dict) -> str:
        return str(item.get("chunk_id") or item.get("citation") or item.get("reference_path") or item.get("title"))

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
                "top_page_index_score": 0.0,
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
        merged: dict[str, dict] = {}
        for hit in self._lookup_vector_exact_reference(query, top_k):
            self._merge_hit(merged, hit, semantic_score=1.0, page_index_score=0.0, retrieval_mode="semantic")
        for hit in self.page_index.lookup_exact_reference(query, top_k):
            self._merge_hit(
                merged,
                hit,
                semantic_score=0.0,
                page_index_score=hit.get("page_index_score", hit.get("score", 0.0)),
                retrieval_mode="page_index",
            )
        exact_hits = list(merged.values())
        exact_hits.sort(
            key=lambda item: (
                float(item.get("page_index_score", 0.0)),
                float(item.get("semantic_score", 0.0)),
            ),
            reverse=True,
        )
        return exact_hits[:top_k]

    def _lookup_vector_exact_reference(self, query: str, top_k: int) -> list[dict]:
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
            exact_item["semantic_score"] = bonus
            exact_item["page_index_score"] = 0.0
            exact_item["retrieval_modes"] = ["semantic"]
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
        if "information technology act" in normalized_query or re.search(r"\bit act\b", normalized_query):
            return "it_act"
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
        if statute == "it_act":
            return (
                source_id == "it_act_2000"
                or source_id.startswith("it_act")
                or "information technology act" in haystack
                or "act no. 21 of 2000" in haystack
            )
        return False

    def _decompose_query(self, query: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", query.strip())
        if len(normalized.split()) < 12:
            return [normalized]

        fragments = re.split(r"[?;]|(?:\band\b)|(?:\bafter\b)|(?:\bbefore\b)|(?:\bwhile\b)|(?:\bwhere\b)", normalized, flags=re.IGNORECASE)
        query_parts: list[str] = [normalized]
        for fragment in fragments:
            candidate = fragment.strip(" ,.")
            if len(candidate.split()) < 4 or candidate.lower() == normalized.lower():
                continue
            if candidate not in query_parts:
                query_parts.append(candidate)
            if len(query_parts) >= 3:
                break
        return query_parts

    def _expand_query_parts(self, query_parts: list[str]) -> list[str]:
        if not query_parts:
            return []
        base_query = query_parts[0]
        normalized = base_query.lower()
        expanded = list(query_parts)

        if "arrest" in normalized and any(keyword in normalized for keyword in ("right", "rights", "bail", "advocate", "lawyer")):
            expanded.extend(
                [
                    "BNSS section 47 grounds of arrest right to bail",
                    "BNSS section 38 advocate of choice during interrogation",
                    "BNSS section 478 bail for arrested person without warrant",
                ]
            )

        if "fir" in normalized and any(keyword in normalized for keyword in ("cognizable", "register", "registration", "refuse", "refusal")):
            expanded.extend(
                [
                    "BNSS section 173 information relating to cognizable offence free copy to informant",
                    "CrPC section 154 FIR registration cognizable offence refusal police station",
                ]
            )

        if any(keyword in normalized for keyword in ("online payment", "payment fraud", "otp", "cyber fraud", "bank fraud")) or (
            any(keyword in normalized for keyword in ("online", "payment", "otp", "bank", "cyber"))
            and any(keyword in normalized for keyword in ("fraud", "cheating", "scam"))
        ):
            expanded.extend(
                [
                    "Information Technology Act section 66D cheating by personation using computer resource",
                    "BNS section 318 cheating online payment fraud",
                ]
            )

        if "punishment" in normalized and "cheating" in normalized and ("bns" in normalized or "bharatiya nyaya sanhita" in normalized):
            expanded.extend(
                [
                    "BNS section 318(2) punishment for cheating",
                    "BNS section 318(3) punishment for cheating wrongful loss",
                    "BNS section 318(4) punishment for cheating delivery of property",
                ]
            )

        if ("section 187" in normalized or re.search(r"\b187\b", normalized)) and ("bnss" in normalized or "bharatiya nagarik suraksha sanhita" in normalized):
            expanded.append("BNSS section 187 detention magistrate police custody fifteen days ninety days")

        deduped: list[str] = []
        seen: set[str] = set()
        for part in expanded:
            candidate = re.sub(r"\s+", " ", part.strip())
            if not candidate:
                continue
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
        return deduped

    def _rerank_hits(self, query: str, hits: list[dict], top_k: int) -> list[dict]:
        normalized = query.lower()
        wants_bns = "bns" in normalized or "bharatiya nyaya sanhita" in normalized
        wants_bnss = "bnss" in normalized or "bharatiya nagarik suraksha sanhita" in normalized
        wants_ipc_compare = "ipc" in normalized or "compare" in normalized or "comparison" in normalized
        wants_arrest_rights = "arrest" in normalized and any(keyword in normalized for keyword in ("right", "rights", "bail", "advocate", "lawyer"))
        wants_fir_registration = "fir" in normalized and any(keyword in normalized for keyword in ("cognizable", "register", "registration", "refuse", "refusal"))
        wants_online_payment_fraud = any(keyword in normalized for keyword in ("online payment", "payment fraud", "otp", "bank fraud", "cyber fraud")) or (
            any(keyword in normalized for keyword in ("online", "payment", "otp", "bank", "cyber"))
            and any(keyword in normalized for keyword in ("fraud", "cheating", "scam"))
        )
        wants_cheating_punishment = "punishment" in normalized and "cheating" in normalized
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
            if item.get("reference_path"):
                adjusted += 0.03
            if wants_arrest_rights:
                if self._citation_contains(item, "Act No. 46 of 2023 | Section 47") or "grounds of arrest" in haystack or "right to bail" in haystack:
                    adjusted += 0.55
                if self._citation_contains(item, "Act No. 46 of 2023 | Section 38") or "advocate of his choice" in haystack:
                    adjusted += 0.45
                if self._citation_contains(item, "Act No. 46 of 2023 | Section 478"):
                    adjusted -= 0.05
                if self._citation_contains(item, "Act No. 46 of 2023 | Section 187") or self._citation_contains(item, "Act No. 46 of 2023 | Section 83"):
                    adjusted -= 0.16
            if wants_fir_registration:
                if self._citation_contains(item, "Act No. 46 of 2023 | Section 173") or "cognizable offence" in haystack:
                    adjusted += 0.38
                if "free of cost" in haystack or "copy of the information" in haystack:
                    adjusted += 0.12
                if self._citation_contains(item, "Act No. 46 of 2023 | Section 35") or self._citation_contains(item, "Act No. 46 of 2023 | Section 40"):
                    adjusted -= 0.12
            if wants_online_payment_fraud:
                if self._citation_contains(item, "Act No. 21 of 2000 | Section 66D") or "computer resource" in haystack or "personation" in haystack:
                    adjusted += 0.66
                if self._citation_contains(item, "Act No. 45 of 2023 | Section 318"):
                    adjusted += 0.2
                if self._citation_contains(item, "Act No. 45 of 2023 | Section 321") or self._citation_contains(item, "Act No. 45 of 2023 | Section 245"):
                    adjusted -= 0.28
            if wants_cheating_punishment:
                if self._citation_contains(item, "Act No. 45 of 2023 | Section 318(2)"):
                    adjusted += 0.24
                if self._citation_contains(item, "Act No. 45 of 2023 | Section 318(3)"):
                    adjusted += 0.16
                if self._citation_contains(item, "Act No. 45 of 2023 | Section 318(4)"):
                    adjusted += 0.16
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

        if wants_online_payment_fraud:
            cyber_hits: list[dict] = []
            primary: list[dict] = []
            for item in reranked:
                haystack = f"{item.get('title', '')} {item.get('citation', '')}".lower()
                if "section 66d" in haystack or "information technology act" in haystack:
                    cyber_hits.append(item)
                else:
                    primary.append(item)
            merged: list[dict] = []
            if cyber_hits:
                merged.append(cyber_hits[0])
            merged.extend(primary[: max(top_k - len(merged), 0)])
            if len(merged) < top_k:
                seen_ids = {id(row) for row in merged}
                merged.extend([row for row in reranked if id(row) not in seen_ids][: top_k - len(merged)])
            return merged[:top_k]

        return reranked[:top_k]

    def _citation_contains(self, item: dict, needle: str) -> bool:
        return needle.lower() in str(item.get("citation", "")).lower()
