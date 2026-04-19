from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from app.core.config import Settings


SECTION_REFERENCE_REGEX = re.compile(r"\bsection\s+(\d+[A-Za-z-]*)(?:\(([\da-zA-Z]+)\))?", re.IGNORECASE)
CHAPTER_REGEX = re.compile(r"\bchapter\s+([ivxlcdm\d]+[a-zA-Z-]*)\b", re.IGNORECASE)
CLAUSE_REGEX = re.compile(r"^\(([a-z\d]+)\)\s+", re.IGNORECASE)
TOKEN_REGEX = re.compile(r"[a-z0-9]{3,}")

COMMON_STOPWORDS = {
    "about",
    "after",
    "against",
    "also",
    "been",
    "before",
    "between",
    "could",
    "every",
    "from",
    "have",
    "into",
    "legal",
    "law",
    "laws",
    "more",
    "must",
    "next",
    "only",
    "other",
    "plain",
    "section",
    "sections",
    "shall",
    "should",
    "that",
    "their",
    "them",
    "there",
    "these",
    "this",
    "under",
    "what",
    "when",
    "which",
    "with",
    "would",
    "your",
}

ACT_ALIASES = {
    "bns": (
        "bns",
        "bharatiya nyaya sanhita",
        "act no. 45 of 2023",
    ),
    "bnss": (
        "bnss",
        "bharatiya nagarik suraksha sanhita",
        "act no. 46 of 2023",
    ),
    "bsa": (
        "bsa",
        "bharatiya sakshya adhiniyam",
        "act no. 47 of 2023",
    ),
    "ipc": (
        "ipc",
        "indian penal code",
        "act no. 45 of 1860",
    ),
    "crpc": (
        "crpc",
        "code of criminal procedure",
        "act no. 2 of 1974",
    ),
    "dpdp": (
        "dpdp",
        "digital personal data protection act",
        "personal data protection act",
        "act no. 22 of 2023",
    ),
    "contract_act": (
        "contract act",
        "indian contract act",
    ),
    "evidence_act": (
        "indian evidence act",
        "evidence act",
    ),
}

ACT_TITLES = {
    "bns": "Bharatiya Nyaya Sanhita, 2023",
    "bnss": "Bharatiya Nagarik Suraksha Sanhita, 2023",
    "bsa": "Bharatiya Sakshya Adhiniyam, 2023",
    "ipc": "Indian Penal Code, 1860",
    "crpc": "Code of Criminal Procedure, 1973",
    "dpdp": "Digital Personal Data Protection Act, 2023",
    "contract_act": "Indian Contract Act, 1872",
    "evidence_act": "Indian Evidence Act, 1872",
}


class PageIndexStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.index_path: Path = settings.page_index_path
        self.payload: dict | None = None
        self.nodes: list[dict] = []
        self.citation_lookup: dict[str, list[int]] = {}

    def exists(self) -> bool:
        return self.index_path.exists()

    def build(self, records: list[dict]) -> None:
        acts: dict[str, dict] = {}
        nodes: list[dict] = []
        citation_lookup: dict[str, list[int]] = defaultdict(list)

        for record in records:
            node = self._record_to_node(record)
            node_index = len(nodes)
            nodes.append(node)

            act_bucket = acts.setdefault(
                node["act_id"],
                {
                    "act_id": node["act_id"],
                    "title": node["act_title"],
                    "aliases": node["act_aliases"],
                    "source_ids": [],
                    "section_count": 0,
                    "sections": {},
                    "chapters": {},
                },
            )
            if node["source_id"] and node["source_id"] not in act_bucket["source_ids"]:
                act_bucket["source_ids"].append(node["source_id"])

            chapter_bucket = act_bucket["chapters"].setdefault(
                node["chapter_id"],
                {
                    "chapter_id": node["chapter_id"],
                    "label": node["chapter_label"],
                    "section_ids": [],
                },
            )
            if node["section_id"] not in chapter_bucket["section_ids"]:
                chapter_bucket["section_ids"].append(node["section_id"])

            section_bucket = act_bucket["sections"].setdefault(
                node["section_id"],
                {
                    "section_id": node["section_id"],
                    "section_number": node["section_number"],
                    "citation": node["citation"],
                    "reference_path": node["reference_path"],
                    "chunk_ids": [],
                    "linked_citations": [],
                    "clause_ids": [],
                },
            )
            section_bucket["chunk_ids"].append(node["chunk_id"])
            for linked_citation in node["linked_citations"]:
                if linked_citation not in section_bucket["linked_citations"]:
                    section_bucket["linked_citations"].append(linked_citation)
            if node["clause_id"] and node["clause_id"] not in section_bucket["clause_ids"]:
                section_bucket["clause_ids"].append(node["clause_id"])

            for citation_key in filter(None, {self._citation_key(node["citation"]), *[self._citation_key(value) for value in node["linked_citations"]]}):
                citation_lookup[citation_key].append(node_index)

        for act in acts.values():
            act["section_count"] = len(act["sections"])

        payload = {
            "version": 1,
            "record_count": len(nodes),
            "acts": acts,
            "nodes": nodes,
            "citation_lookup": {key: value for key, value in citation_lookup.items()},
        }
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        self.payload = payload
        self.nodes = nodes
        self.citation_lookup = payload["citation_lookup"]

    def load(self) -> None:
        if self.payload is None:
            self.payload = json.loads(self.index_path.read_text(encoding="utf-8"))
            self.nodes = self.payload.get("nodes", [])
            self.citation_lookup = self.payload.get("citation_lookup", {})

    def search(self, query: str, top_k: int) -> list[dict]:
        self.load()
        plan = self._analyze_query(query)
        exact_hits = self.lookup_exact_reference(query, top_k=max(top_k, 2))
        ranked: list[dict] = exact_hits[:]
        seen_keys = {self._result_key(item) for item in ranked}

        candidate_indexes = self._candidate_indexes(plan)
        structural_hits: list[dict] = []
        for index in candidate_indexes:
            node = self.nodes[index]
            score, reasons = self._score_node(plan, node)
            if score <= 0:
                continue
            hit = self._node_to_result(node, score=score, reasons=reasons)
            key = self._result_key(hit)
            if key in seen_keys:
                continue
            structural_hits.append(hit)

        structural_hits.sort(key=lambda item: item["score"], reverse=True)
        ranked.extend(structural_hits[: max(top_k * 2, top_k)])

        expanded = self._expand_linked_sections(ranked, top_k=max(top_k * 2, top_k))
        merged: list[dict] = []
        seen_keys.clear()
        for item in ranked + expanded:
            key = self._result_key(item)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append(item)
        merged.sort(key=lambda item: item["score"], reverse=True)
        return merged[:top_k]

    def lookup_exact_reference(self, query: str, top_k: int) -> list[dict]:
        self.load()
        plan = self._analyze_query(query)
        if not plan["section_references"]:
            return []

        exact_hits: list[dict] = []
        for reference in plan["section_references"]:
            citation_keys = [self._citation_key(f"Section {reference['section']}")]
            if reference["clause"]:
                citation_keys.insert(0, self._citation_key(f"Section {reference['section']}({reference['clause']})"))
            for citation_key in citation_keys:
                for index in self.citation_lookup.get(citation_key, []):
                    node = self.nodes[index]
                    if plan["act_ids"] and node["act_id"] not in plan["act_ids"]:
                        continue
                    exact_hits.append(
                        self._node_to_result(
                            node,
                            score=0.98 if reference["clause"] else 0.92,
                            reasons=["Exact citation match in PageIndex"],
                        )
                    )
        exact_hits.sort(key=lambda item: item["score"], reverse=True)
        deduped: list[dict] = []
        seen_keys: set[str] = set()
        for item in exact_hits:
            key = self._result_key(item)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(item)
        return deduped[:top_k]

    def get_structure_overview(self, query: str) -> dict | None:
        self.load()
        plan = self._analyze_query(query)
        if not plan["act_ids"]:
            return None
        act_id = plan["act_ids"][0]
        act = self.payload["acts"].get(act_id) if self.payload else None
        if not act:
            return None
        return {
            "act_id": act_id,
            "title": act["title"],
            "section_count": act["section_count"],
            "chapter_count": len(act["chapters"]),
        }

    def _candidate_indexes(self, plan: dict) -> list[int]:
        if not self.nodes:
            return []
        if not plan["act_ids"]:
            return list(range(len(self.nodes)))
        return [index for index, node in enumerate(self.nodes) if node["act_id"] in plan["act_ids"]]

    def _expand_linked_sections(self, hits: list[dict], top_k: int) -> list[dict]:
        self.load()
        expanded: list[dict] = []
        seen_keys = {self._result_key(item) for item in hits}
        for hit in hits[: max(top_k // 2, 1)]:
            for linked_citation in hit.get("linked_citations", [])[:3]:
                citation_key = self._citation_key(linked_citation)
                for index in self.citation_lookup.get(citation_key, []):
                    node = self.nodes[index]
                    candidate = self._node_to_result(
                        node,
                        score=0.46,
                        reasons=[f"Linked section expansion from {hit.get('citation', 'retrieved section')}"],
                    )
                    key = self._result_key(candidate)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    expanded.append(candidate)
        expanded.sort(key=lambda item: item["score"], reverse=True)
        return expanded[:top_k]

    def _score_node(self, plan: dict, node: dict) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []
        if plan["act_ids"] and node["act_id"] in plan["act_ids"]:
            score += 0.32
            reasons.append("Act matched the query domain")

        for reference in plan["section_references"]:
            if node["section_number"] == reference["section"]:
                score += 0.34
                reasons.append("Section matched the requested citation")
                if reference["clause"] and node["clause_id"] == reference["clause"]:
                    score += 0.12
                    reasons.append("Clause matched the requested subsection")

        if plan["chapter_ids"] and node["chapter_id"] in plan["chapter_ids"]:
            score += 0.14
            reasons.append("Chapter matched the query")

        overlap = self._token_overlap(plan["keywords"], node["search_terms"])
        if overlap:
            lexical_score = min(0.22, overlap / max(len(plan["keywords"]), 1))
            score += lexical_score
            reasons.append("Legal topic keywords aligned with the indexed section text")

        if plan["asks_for_penalty"] and any(term in node["text_lower"] for term in ("punished", "imprisonment", "fine")):
            score += 0.08
            reasons.append("Section contains punishment language")
        if plan["asks_for_procedure"] and any(term in node["text_lower"] for term in ("procedure", "magistrate", "investigation", "complaint", "police")):
            score += 0.07
            reasons.append("Section contains procedural language")
        if plan["asks_for_rights"] and any(term in node["text_lower"] for term in ("right", "bail", "arrest", "inform", "notice")):
            score += 0.07
            reasons.append("Section contains rights-related language")

        return min(score, 1.0), reasons

    def _token_overlap(self, query_terms: set[str], node_terms: list[str]) -> int:
        if not query_terms or not node_terms:
            return 0
        return sum(1 for token in query_terms if token in node_terms)

    def _record_to_node(self, record: dict) -> dict:
        act_id, act_title, act_aliases = self._infer_act(record)
        chapter_id, chapter_label = self._infer_chapter(record)
        section_number, clause_id = self._infer_section_and_clause(record)
        section_id = section_number or "unstructured"
        reference_parts = [act_title]
        if chapter_label and chapter_id != "chapter_unspecified":
            reference_parts.append(chapter_label)
        if section_number:
            reference_parts.append(f"Section {section_number}")
        if clause_id:
            reference_parts.append(f"Clause {clause_id}")

        linked_citations = record.get("linked_citations", [])
        if not isinstance(linked_citations, list):
            linked_citations = []

        search_terms = sorted(
            set(
                TOKEN_REGEX.findall(
                    " ".join(
                        [
                            str(record.get("title", "")).lower(),
                            str(record.get("citation", "")).lower(),
                            str(record.get("summary", "")).lower(),
                            str(record.get("text", "")).lower(),
                            " ".join(str(item).lower() for item in linked_citations),
                        ]
                    )
                )
            )
            - COMMON_STOPWORDS
        )

        return {
            "chunk_id": record.get("chunk_id") or record.get("document_id") or str(record.get("citation", "")),
            "document_id": record.get("document_id"),
            "source_id": record.get("source_id", ""),
            "title": record.get("title", ""),
            "citation": record.get("citation", ""),
            "summary": record.get("summary", ""),
            "text": record.get("text", ""),
            "source_type": record.get("source_type", "statute"),
            "document_type": record.get("document_type", record.get("source_type", "act")),
            "source_url": record.get("source_url"),
            "linked_citations": linked_citations,
            "chunk_strategy": record.get("chunk_strategy", ""),
            "act_id": act_id,
            "act_title": act_title,
            "act_aliases": list(act_aliases),
            "chapter_id": chapter_id,
            "chapter_label": chapter_label,
            "section_id": section_id,
            "section_number": section_number,
            "clause_id": clause_id,
            "reference_path": " > ".join(part for part in reference_parts if part),
            "search_terms": search_terms,
            "text_lower": str(record.get("text", "")).lower(),
        }

    def _infer_act(self, record: dict) -> tuple[str, str, tuple[str, ...]]:
        haystack = " ".join(
            [
                str(record.get("source_id", "")).lower(),
                str(record.get("title", "")).lower(),
                str(record.get("citation", "")).lower(),
                str(record.get("summary", "")).lower(),
            ]
        )
        for act_id, aliases in ACT_ALIASES.items():
            if any(alias in haystack for alias in aliases):
                return act_id, ACT_TITLES.get(act_id, record.get("title", "Unknown Act")), aliases
        fallback_id = re.sub(r"[^a-z0-9]+", "_", str(record.get("source_id") or record.get("title") or "legal_document").lower()).strip("_")
        fallback_title = str(record.get("title") or record.get("citation") or "Legal Document")
        return fallback_id or "legal_document", fallback_title, tuple()

    def _infer_chapter(self, record: dict) -> tuple[str, str]:
        for field in ("citation", "title", "text"):
            value = str(record.get(field, ""))
            match = CHAPTER_REGEX.search(value)
            if match:
                chapter_label = f"Chapter {match.group(1).upper()}"
                chapter_id = re.sub(r"[^a-z0-9]+", "_", chapter_label.lower()).strip("_")
                return chapter_id, chapter_label
        return "chapter_unspecified", "Chapter Unspecified"

    def _infer_section_and_clause(self, record: dict) -> tuple[str | None, str | None]:
        citation = str(record.get("citation", ""))
        exact_section_match = re.search(r"\|\s*section\s+(\d+[A-Za-z-]*)(?:\(([\da-zA-Z]+)\))?", citation, flags=re.IGNORECASE)
        if exact_section_match:
            return exact_section_match.group(1), exact_section_match.group(2)

        reference_matches = list(SECTION_REFERENCE_REGEX.finditer(citation))
        if reference_matches:
            match = reference_matches[-1]
            return match.group(1), match.group(2)

        text = str(record.get("text", ""))
        inline_match = SECTION_REFERENCE_REGEX.search(text)
        if inline_match:
            return inline_match.group(1), inline_match.group(2)

        clause_match = CLAUSE_REGEX.search(text.strip())
        return None, clause_match.group(1) if clause_match else None

    def _analyze_query(self, query: str) -> dict:
        normalized = query.lower()
        keywords = {
            token for token in TOKEN_REGEX.findall(normalized)
            if token not in COMMON_STOPWORDS
        }
        act_ids = [act_id for act_id, aliases in ACT_ALIASES.items() if any(alias in normalized for alias in aliases)]
        chapter_ids = []
        chapter_match = CHAPTER_REGEX.search(normalized)
        if chapter_match:
            chapter_label = f"chapter_{chapter_match.group(1).lower()}"
            chapter_ids.append(re.sub(r"[^a-z0-9]+", "_", chapter_label).strip("_"))
        section_references = [
            {"section": match.group(1), "clause": match.group(2)}
            for match in SECTION_REFERENCE_REGEX.finditer(normalized)
        ]
        asks_for_penalty = any(term in normalized for term in ("punishment", "punish", "sentence", "fine", "imprisonment"))
        asks_for_procedure = any(term in normalized for term in ("fir", "procedure", "investigation", "register", "complaint", "court", "magistrate"))
        asks_for_rights = any(term in normalized for term in ("rights", "right", "bail", "arrest", "detention"))
        return {
            "normalized": normalized,
            "keywords": keywords,
            "act_ids": act_ids,
            "chapter_ids": chapter_ids,
            "section_references": section_references,
            "asks_for_penalty": asks_for_penalty,
            "asks_for_procedure": asks_for_procedure,
            "asks_for_rights": asks_for_rights,
        }

    def _node_to_result(self, node: dict, score: float, reasons: list[str]) -> dict:
        result = {
            "chunk_id": node["chunk_id"],
            "document_id": node["document_id"],
            "source_id": node["source_id"],
            "title": node["title"],
            "citation": node["citation"],
            "text": node["text"],
            "summary": node["summary"],
            "source_type": node["source_type"],
            "document_type": node["document_type"],
            "source_url": node.get("source_url"),
            "linked_citations": node.get("linked_citations", []),
            "chunk_strategy": node.get("chunk_strategy", ""),
            "score": round(score, 6),
            "page_index_score": round(score, 6),
            "semantic_score": 0.0,
            "retrieval_modes": ["page_index"],
            "retrieval_mode": "page_index",
            "reference_path": node["reference_path"],
            "page_index_reasoning": "; ".join(reasons),
        }
        return result

    def _result_key(self, item: dict) -> str:
        return str(item.get("chunk_id") or item.get("citation") or item.get("reference_path") or item.get("title"))

    def _citation_key(self, citation: str) -> str:
        return re.sub(r"\s+", " ", citation.strip().lower())
