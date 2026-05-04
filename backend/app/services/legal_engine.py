from __future__ import annotations

import json
import re
from collections import Counter
from textwrap import dedent

from fastapi import HTTPException, UploadFile

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.fir import FIRIntelligence, FIRRecord
from app.schemas.analysis import (
    CaseAnalysisRequest,
    CaseAnalysisResponse,
    CaseStrengthRequest,
    CaseStrengthResponse,
    DraftGenerationRequest,
    DraftGenerationResponse,
    FirDraftRequest,
    FirDraftResponse,
    SimilarCaseReference,
)
from app.schemas.chat import ChatRequest, ChatResponse, SourceDocument
from app.schemas.documents import (
    ContractAnalysisResponse,
    ContractClause,
    EvidenceAnalysisResponse,
    EvidenceEntity,
)
from app.schemas.research import ResearchCaseResult, ResearchFIRAnalysis, ResearchRequest, ResearchResponse
from app.services.document_ingestion import DocumentIngestionService
from app.services.inference import InferenceGateway
from app.services.retriever import Retriever


class LegalEngine:
    def __init__(
        self,
        settings: Settings,
        retriever: Retriever,
        inference: InferenceGateway,
        document_ingestion: DocumentIngestionService,
    ) -> None:
        self.settings = settings
        self.retriever = retriever
        self.inference = inference
        self.document_ingestion = document_ingestion

    def answer_question(self, payload: ChatRequest) -> ChatResponse:
        structural_response = self._resolve_structural_statute_question(payload.question)
        if structural_response:
            return structural_response

        contextual_question = self._build_contextual_question(payload)
        scope = self.retriever.assess_scope(contextual_question)
        if not scope["in_scope"]:
            return self._out_of_scope_response(scope)
        prioritized_hits = self._filter_grounded_hits(self._dedupe_hits(self._prioritize_hits_for_question(contextual_question, scope["hits"])))
        if not prioritized_hits:
            return self._insufficient_grounding_response()
        sources = self._build_source_documents(prioritized_hits)
        if not self._has_grounded_sources(sources):
            return self._insufficient_grounding_response()
        context = self._format_sources_for_prompt(sources)
        if self.settings.inference_provider.lower() == "mock":
            parsed = self._synthesize_chat_answer(payload.question, sources, payload.history)
        else:
            history_context = self._format_history_for_prompt(payload.history)
            prompt = dedent(
                f"""
                Conversation context:
                {history_context or '[No prior conversation context]'}

                User question: {payload.question}
                Retrieval query used: {contextual_question}
                Preferred language: {payload.language}

                Retrieved legal context:
                {context}

                Answer only from the retrieved context.
                Return strict JSON with keys "answer" and "reasoning".
                The answer must be plain-language, human-readable, cite the most relevant sections or authorities, and give practical next steps when appropriate.
                """
            ).strip()
            generated = self.inference.generate(
                "You are NyayaSetu, a self-hosted legal assistant focused on Indian law.",
                prompt,
            )
            parsed = self._parse_generation(generated)
        answer = parsed.get("answer") or self._fallback_answer(sources)
        if not self._answer_is_grounded(answer, sources):
            return self._insufficient_grounding_response()
        return ChatResponse(
            answer=answer,
            reasoning=parsed.get("reasoning") or "The answer is grounded in the retrieved legal materials listed below.",
            sources=sources,
            in_scope=True,
        )

    def analyze_case(self, payload: CaseAnalysisRequest) -> CaseAnalysisResponse:
        query = self._boost_legal_query(" ".join(
            [
                payload.incident_description,
                payload.location or "",
                payload.incident_date or "",
                " ".join(payload.evidence),
            ]
        ).strip())
        sources = self._retrieve_sources(query)
        laws = [source.citation for source in sources]
        case_type = self._infer_case_type(payload.incident_description, laws)
        parties = payload.people_involved or self._infer_parties(payload.incident_description)
        key_facts = self._extract_case_facts(payload.incident_description, payload.location, payload.incident_date)
        legal_issues = self._infer_legal_issues(payload.incident_description, sources)
        strengths = self._derive_case_strengths(payload.incident_description, payload.evidence, sources)
        weaknesses = self._derive_case_weaknesses(payload.incident_description, payload.evidence, payload.location)
        missing_elements = self._derive_missing_case_elements(payload)
        suggested_actions = self._suggest_case_actions(case_type, payload.evidence)
        possible_outcomes = self._infer_possible_outcomes(case_type, sources)
        possible_punishment = self._summarize_possible_punishment(sources)
        final_analysis = self._compose_case_analysis_summary(
            case_type,
            laws,
            strengths,
            weaknesses,
            missing_elements,
        )
        similar_cases = self._extract_verified_case_references(sources)
        return CaseAnalysisResponse(
            case_type=case_type,
            parties=parties,
            legal_sections=laws,
            key_facts=key_facts,
            legal_issues=legal_issues,
            strengths=strengths,
            weaknesses=weaknesses,
            missing_elements=missing_elements,
            possible_outcomes=possible_outcomes,
            suggested_actions=suggested_actions,
            similar_cases=similar_cases,
            final_analysis=final_analysis,
            case_summary=f"{case_type.title()} matter involving {len(parties) or 1} primary parties.",
            applicable_laws=laws,
            legal_reasoning=self._fallback_reasoning(sources),
            possible_punishment=possible_punishment,
            evidence_required=self._suggest_evidence(payload.evidence),
            recommended_next_steps=suggested_actions,
            sources=sources,
        )

    def score_case_strength(self, payload: CaseStrengthRequest) -> CaseStrengthResponse:
        description = (payload.case_description or "").strip()
        if description:
            evidence_items = self._estimate_evidence_items(description)
            witness_count = self._estimate_witness_count(description)
            documentary_support = payload.documentary_support or self._has_documentary_support(description)
            police_complaint_filed = payload.police_complaint_filed or bool(
                re.search(r"\b(fir|complaint filed|police complaint|nc complaint)\b", description, flags=re.IGNORECASE)
            )
            incident_recency_days = payload.incident_recency_days
            jurisdiction_match = payload.jurisdiction_match
            sources = self._retrieve_sources(self._boost_legal_query(description))
            case_type = self._infer_case_type(description, [source.citation for source in sources])
        else:
            evidence_items = payload.evidence_items or 0
            witness_count = payload.witness_count or 0
            documentary_support = payload.documentary_support
            police_complaint_filed = payload.police_complaint_filed
            incident_recency_days = payload.incident_recency_days
            jurisdiction_match = payload.jurisdiction_match
            sources = []
            case_type = "criminal"

        score = 24
        key_strengths: list[str] = []
        key_weaknesses: list[str] = []
        missing_elements: list[str] = []

        score += min(evidence_items * 9, 27)
        if evidence_items:
            key_strengths.append("The narrative already points to documentary or digital evidence.")
        else:
            key_weaknesses.append("The case currently lacks clearly described primary evidence.")
            missing_elements.append("Upload or preserve screenshots, documents, CCTV, receipts, or device records.")

        score += min(witness_count * 6, 18)
        if witness_count:
            key_strengths.append("Witness support improves corroboration.")
        else:
            key_weaknesses.append("No independent witness support is described yet.")

        if documentary_support:
            score += 14
            key_strengths.append("Documentary support reduces ambiguity about the sequence of events.")
        else:
            missing_elements.append("Add contracts, notices, bills, bank records, or other written proof if available.")

        if police_complaint_filed:
            score += 10
            key_strengths.append("A prior formal complaint helps preserve chronology.")
        elif case_type == "criminal":
            key_weaknesses.append("No contemporaneous police or formal complaint is mentioned.")

        if incident_recency_days <= 30:
            score += 8
            key_strengths.append("Recent incidents are usually easier to verify.")
        else:
            key_weaknesses.append("Delay can create evidentiary and recollection issues.")

        if not jurisdiction_match:
            score -= 15
            key_weaknesses.append("Jurisdiction mismatch may delay maintainability and forum selection.")
            missing_elements.append("Confirm the correct police station, court, or territorial jurisdiction.")

        if description:
            if len(description.split()) >= 40:
                score += 6
                key_strengths.append("The factual narrative is reasonably detailed and internally coherent.")
            else:
                key_weaknesses.append("The narrative is still short and may miss important legal facts.")
            if case_type == "criminal":
                score += 4
            if case_type == "civil" and documentary_support:
                score += 8
                key_strengths.append("Civil maintainability looks stronger because written proof is already mentioned.")
            if not self._extract_verified_case_references(sources):
                missing_elements.append("Verified court-case support is unavailable until a case-law dataset is indexed.")

        score = max(0, min(score, 100))
        strength_label = "Strong Case" if score >= 71 else "Moderate Case" if score >= 41 else "Weak Case"
        suggested_sections = [source.citation for source in sources[:5]]
        similar_cases = self._extract_verified_case_references(sources)
        rationale = [*key_strengths, *key_weaknesses]
        final_analysis = self._compose_case_strength_summary(
            score,
            strength_label,
            key_strengths,
            key_weaknesses,
            missing_elements,
            suggested_sections,
            bool(similar_cases),
        )
        return CaseStrengthResponse(
            case_strength_score=score,
            strength_label=strength_label,
            key_strengths=key_strengths or ["The legal score is provisional and will improve with stronger evidence details."],
            key_weaknesses=key_weaknesses or ["No major structural weakness was detected from the limited inputs."],
            missing_elements=list(dict.fromkeys(missing_elements)),
            suggested_sections=suggested_sections,
            similar_cases=similar_cases,
            final_analysis=final_analysis,
            score=score,
            verdict=strength_label,
            rationale=rationale or ["The current score is based on limited structured indicators."],
        )

    def generate_draft(self, payload: DraftGenerationRequest) -> DraftGenerationResponse:
        prompt = dedent(
            f"""
            Draft type: {payload.draft_type}
            Parties: {", ".join(payload.parties)}
            Facts: {payload.facts}
            Relief sought: {payload.relief_sought}
            Jurisdiction: {payload.jurisdiction}

            Produce a structured legal draft with placeholders where facts are missing.
            """
        ).strip()
        generated = self.inference.generate(
            "Draft a formal Indian legal document in a professional tone.",
            prompt,
        )
        parsed = self._parse_generation(generated)
        content = parsed.get("answer") or dedent(
            f"""
            {payload.draft_type.upper()}

            Parties:
            {chr(10).join(f"- {party}" for party in payload.parties) or "- [Insert parties]"}

            Facts:
            {payload.facts}

            Relief Sought:
            {payload.relief_sought or "[Insert relief sought]"}

            Jurisdiction:
            {payload.jurisdiction or "[Insert jurisdiction]"}

            Verification:
            I state that the facts mentioned above are true to the best of my knowledge and belief.
            """
        ).strip()
        return DraftGenerationResponse(
            draft_type=payload.draft_type,
            content=content,
            notes=[
                "Review party names, dates, and jurisdiction before use.",
                "Replace placeholders with verified facts and annexures.",
                "Have counsel validate format and court-specific requirements.",
            ],
        )

    def generate_fir(self, payload: FirDraftRequest) -> FirDraftResponse:
        sections = payload.applicable_sections or [source.citation for source in self._retrieve_sources(payload.incident_description)]
        fir_text = dedent(
            f"""
            To,
            The Station House Officer
            {payload.police_station}

            Subject: Complaint regarding cognizable offence

            I, {payload.complainant_name}, residing at {payload.complainant_address}, submit this complaint regarding the incident that occurred on {payload.incident_date} at {payload.incident_location}.

            Incident Description:
            {payload.incident_description}

            Relevant Sections:
            {", ".join(sections)}

            I request registration of an FIR, protection of evidence, and investigation in accordance with law.

            Signature:
            {payload.complainant_name}
            """
        ).strip()
        checklist = [
            "Carry identity proof and address proof.",
            "Attach screenshots, recordings, medical records, or other primary evidence.",
            "Request a receiving copy or FIR number after filing.",
        ]
        return FirDraftResponse(fir_text=fir_text, sections=sections, filing_checklist=checklist)

    def research(self, payload: ResearchRequest) -> ResearchResponse:
        query = payload.effective_query
        boosted_query = self._boost_legal_query(query)
        hits = self._retrieve_sources(boosted_query, payload.top_k)
        display_hits = hits[: payload.top_k]
        summary = "Hybrid retrieval combined semantic RAG hits with PageIndex section navigation for this legal research query."

        if payload.mode == "fir_analysis" and payload.user_role != "premium":
            return ResearchResponse(
                status="success",
                mode=payload.mode,
                results=[],
                fir_analysis=ResearchFIRAnalysis(
                    improved_draft="",
                    suggested_sections="",
                    risk_analysis="Upgrade required to access FIR intelligence features.",
                ),
                message="Upgrade required to access FIR intelligence features.",
                summary=summary,
                hits=display_hits,
            )

        if payload.mode == "fir_analysis":
            fir_analysis = self._analyze_fir_intelligence(query)
            return ResearchResponse(
                status="success",
                mode=payload.mode,
                results=[],
                fir_analysis=fir_analysis,
                message="FIR intelligence generated from grounded statute retrieval and saved FIR comparisons.",
                summary=summary,
                hits=display_hits,
            )

        case_law_hits = (
            self._build_source_documents(self.retriever.search_case_law(boosted_query, top_k=max(payload.top_k, 10)))
            if self._should_search_case_law(query)
            else []
        )
        case_results = self._build_case_search_results(case_law_hits)
        display_hits = self._dedupe_sources([*case_law_hits[: payload.top_k], *display_hits])[: payload.top_k]
        message = None
        if not case_results:
            message = (
                "No verified Supreme Court or High Court matches were found in the currently indexed dataset. "
                "Statutory guidance is shown separately until a case-law corpus is added."
            )
        return ResearchResponse(
            status="success",
            mode=payload.mode,
            results=case_results,
            fir_analysis=ResearchFIRAnalysis(),
            message=message,
            summary=summary,
            hits=display_hits,
        )

    def _dedupe_sources(self, sources: list[SourceDocument]) -> list[SourceDocument]:
        deduped: list[SourceDocument] = []
        seen: set[str] = set()
        for source in sources:
            key = f"{source.citation}|{source.source_url}|{source.title}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(source)
        return deduped

    def _should_search_case_law(self, query: str) -> bool:
        normalized = query.lower()
        explicit_statute_reference = bool(
            re.search(r"\bsection\s+\d+[a-zA-Z-]*(?:\([\da-zA-Z]+\))?", normalized)
            and any(term in normalized for term in ("bns", "bnss", "bsa", "ipc", "crpc", "dpdp", "act"))
        )
        case_law_intent = any(
            term in normalized
            for term in (
                "case",
                "cases",
                "judgment",
                "judgement",
                "precedent",
                "citation",
                "court",
                "verdict",
                "similar",
                "acquittal",
                "appeal",
                "trial",
            )
        )
        return case_law_intent or not explicit_statute_reference

    async def analyze_contract(
        self,
        contract_file: UploadFile | None,
        contract_text: str | None,
        user_id: str | None = None,
    ) -> ContractAnalysisResponse:
        _ = user_id
        text = await self._resolve_text(contract_file, contract_text, "contract text or upload")
        contract_type = self._detect_contract_type(text)
        parties = self._extract_contract_parties(text)
        clauses = self._extract_clauses(text)
        missing = self._missing_contract_clauses(text)
        risk_score = self._score_contract_risk(clauses, missing)
        risk_level = "High" if risk_score >= 67 else "Moderate" if risk_score >= 34 else "Low"
        key_risks = [clause.issue for clause in clauses if clause.risk_level in {"High", "Medium"}]
        negotiation_insights = self._contract_negotiation_insights(clauses, missing)
        final_summary = (
            f"This {contract_type.lower()} appears {risk_level.lower()} risk based on the current clause balance, "
            "liability structure, and drafting completeness."
        )
        return ContractAnalysisResponse(
            contract_type=contract_type,
            parties=parties,
            risk_score=risk_score,
            risk_level=risk_level,
            key_risks=key_risks,
            missing_clauses=missing,
            clauses=clauses,
            negotiation_insights=negotiation_insights,
            final_summary=final_summary,
            summary=final_summary,
        )

    async def analyze_evidence(
        self,
        evidence_file: UploadFile | None,
        evidence_text: str | None,
        user_id: str | None = None,
    ) -> EvidenceAnalysisResponse:
        _ = user_id
        text = await self._resolve_text(evidence_file, evidence_text, "evidence text or upload")
        entities = self._extract_entities(text)
        timeline = self._extract_timeline(text)
        observations = [
            "Check source authenticity and metadata before submission.",
            "Preserve the original file hash and device source.",
        ]
        return EvidenceAnalysisResponse(
            extracted_text=text[:2500],
            entities=entities,
            timeline=timeline,
            observations=observations,
        )

    async def _resolve_text(self, upload: UploadFile | None, text: str | None, field_name: str) -> str:
        if text:
            return text
        if upload:
            return await self.document_ingestion.extract_text(upload)
        raise HTTPException(status_code=400, detail=f"Provide {field_name}.")

    def _retrieve_sources(self, query: str, top_k: int | None = None) -> list[SourceDocument]:
        results = self.retriever.search(query, top_k)
        return self._build_source_documents(results)

    def _build_source_documents(self, hits: list[dict]) -> list[SourceDocument]:
        return [
            SourceDocument(
                title=item["title"],
                citation=item["citation"],
                excerpt=(item.get("summary") or item["text"])[:420],
                source_type=item.get("source_type", "statute"),
                score=round(item["score"], 4),
                source_url=item.get("source_url") or self._default_source_url(item["citation"], item["title"]),
                reference_path=item.get("reference_path"),
                retrieval_mode=item.get("retrieval_mode"),
                confidence=round(float(item.get("confidence", item.get("score", 0.0))), 4) if item.get("score") is not None else None,
                metadata=self._source_metadata(item),
            )
            for item in hits
        ]

    def _source_metadata(self, item: dict) -> dict[str, str]:
        metadata: dict[str, str] = {}
        raw_metadata = item.get("metadata")
        if isinstance(raw_metadata, dict):
            for key, value in raw_metadata.items():
                normalized = self._metadata_value_to_string(value)
                if normalized:
                    metadata[str(key)] = normalized
        for key, value in item.items():
            if key in {"metadata", "text"}:
                continue
            normalized = self._metadata_value_to_string(value)
            if normalized:
                metadata[str(key)] = normalized
        return metadata

    def _metadata_value_to_string(self, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        normalized = str(value).strip()
        return normalized

    def _format_sources_for_prompt(self, sources: list[SourceDocument]) -> str:
        formatted: list[str] = []
        for index, source in enumerate(sources, start=1):
            formatted.append(
                "\n".join(
                    [
                        f"[Source {index}] {source.title}",
                        f"Citation: {source.citation}",
                        f"Reference path: {source.reference_path or source.citation}",
                        f"Type: {source.source_type}",
                        f"Retrieval mode: {source.retrieval_mode or 'semantic'}",
                        f"Confidence: {source.confidence if source.confidence is not None else source.score}",
                        f"Metadata: {source.metadata}" if source.metadata else "",
                        f"Excerpt: {source.excerpt}",
                        f"URL: {source.source_url or 'Unavailable'}",
                    ]
                )
            )
        return "\n\n".join(formatted)

    def _filter_grounded_hits(self, hits: list[dict]) -> list[dict]:
        return [
            item for item in hits
            if item.get("source_url") or self._default_source_url(item.get("citation", ""), item.get("title", ""))
        ]

    def _has_grounded_sources(self, sources: list[SourceDocument]) -> bool:
        return any(source.source_url and source.citation for source in sources)

    def _answer_is_grounded(self, answer: str, sources: list[SourceDocument]) -> bool:
        if not sources:
            return False
        answer_lower = answer.lower()
        if any(source.citation.lower() in answer_lower for source in sources[:3]):
            return True
        return any(
            fragment in answer_lower
            for source in sources[:3]
            for fragment in self._grounding_fragments(source)
        )

    def _out_of_scope_response(self, scope: dict) -> ChatResponse:
        has_legal_intent = scope.get("has_legal_intent", False)
        warning = (
            "Ask a legal question about Indian statutes, BNS or IPC sections, FIRs, contracts, rights, judgments, or legal procedure."
            if not has_legal_intent
            else "Rephrase the question with the exact legal issue, section, act, or procedure so NyayaSetu can retrieve grounded legal authority."
        )
        return ChatResponse(
            answer="This question appears to be outside NyayaSetu's legal assistance scope.",
            reasoning=(
                "NyayaSetu only answers when the query shows legal intent and retrieves grounded legal materials from the indexed corpus."
            ),
            sources=[],
            in_scope=False,
            scope_warning=warning,
        )

    def _insufficient_grounding_response(self) -> ChatResponse:
        return ChatResponse(
            answer="I could not find enough grounded legal authority to answer that safely.",
            reasoning=(
                "NyayaSetu rejected this response because the retrieved material was too weak, ambiguous, or insufficiently official to support a safe legal answer."
            ),
            sources=[],
            in_scope=True,
        )

    def _default_source_url(self, citation: str, title: str) -> str | None:
        haystack = f"{citation} {title}".lower()
        if "bnss" in haystack or "bharatiya nagarik suraksha sanhita" in haystack:
            return "https://www.indiacode.nic.in/handle/123456789/21544"
        if "bns" in haystack or "bharatiya nyaya sanhita" in haystack:
            return "https://www.indiacode.nic.in/handle/123456789/20062"
        if "bsa" in haystack or "bharatiya sakshya adhiniyam" in haystack:
            return "https://www.indiacode.nic.in/handle/123456789/20063"
        if "crpc" in haystack or "code of criminal procedure" in haystack:
            return "https://www.indiacode.nic.in/handle/123456789/15247"
        if "dpdp" in haystack or "digital personal data protection" in haystack:
            return "https://www.indiacode.nic.in/handle/123456789/22037?view_type=browse"
        if "evidence act" in haystack or "65b" in haystack:
            return "https://www.indiacode.nic.in/handle/123456789/2187"
        if "contract act" in haystack:
            return "https://www.indiacode.nic.in/handle/123456789/2185"
        if "ipc" in haystack or "penal code" in haystack:
            return "https://www.indiacode.nic.in/handle/123456789/12850"
        return None

    def _parse_generation(self, generated: str) -> dict:
        candidate = generated.strip()
        if "```" in candidate:
            matches = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, flags=re.DOTALL)
            if matches:
                candidate = matches[0]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return {"answer": candidate.strip(), "reasoning": candidate.strip()}

    def _resolve_structural_statute_question(self, question: str) -> ChatResponse | None:
        normalized = question.lower().strip()
        if not re.search(r"\bhow many\b.*\bsections?\b|\bnumber of sections?\b", normalized):
            return None
        overview = self.retriever.get_structure_overview(question)
        if not overview:
            return None
        title = overview["title"]
        section_count = overview["section_count"]
        chapter_count = overview["chapter_count"]
        source = SourceDocument(
            title=title,
            citation=f"PageIndex structural overview for {title}",
            excerpt=(
                f"The PageIndex hierarchy for {title} currently tracks {section_count} sections "
                f"across {chapter_count} chapter buckets."
            ),
            source_type="statute",
            score=1.0,
            source_url=self._default_source_url(title, title),
            reference_path=title,
            retrieval_mode="page_index",
            confidence=1.0,
        )
        return ChatResponse(
            answer=(
                f"{title} currently has {section_count} indexed sections in NyayaSetu's PageIndex. "
                f"The structural index groups them across {chapter_count} chapter buckets so the assistant can navigate the Act logically."
            ),
            reasoning=(
                "This answer came from the PageIndex document structure rather than semantic similarity. "
                "NyayaSetu uses the act hierarchy directly for structural questions so the reply stays section-grounded and explainable."
            ),
            sources=[source],
            in_scope=True,
        )

    def _prioritize_hits_for_question(self, question: str, hits: list[dict]) -> list[dict]:
        normalized = question.lower()
        prioritized = hits
        if re.search(r"\bbns\b", normalized) or "bharatiya nyaya sanhita" in normalized:
            filtered = [
                item for item in hits
                if "bns" in f"{item.get('title', '')} {item.get('citation', '')} {item.get('text', '')}".lower()
            ]
            if filtered:
                prioritized = filtered
        if re.search(r"\bbnss\b", normalized) or "bharatiya nagarik suraksha sanhita" in normalized:
            filtered = [
                item for item in prioritized
                if "bnss" in f"{item.get('title', '')} {item.get('citation', '')} {item.get('text', '')}".lower()
                or "bharatiya nagarik suraksha sanhita" in f"{item.get('title', '')} {item.get('citation', '')} {item.get('text', '')}".lower()
            ]
            if filtered:
                prioritized = filtered
        if re.search(r"\bbsa\b", normalized) or "bharatiya sakshya adhiniyam" in normalized:
            filtered = [
                item for item in prioritized
                if "bsa" in f"{item.get('title', '')} {item.get('citation', '')} {item.get('text', '')}".lower()
                or "bharatiya sakshya adhiniyam" in f"{item.get('title', '')} {item.get('citation', '')} {item.get('text', '')}".lower()
            ]
            if filtered:
                prioritized = filtered
        if re.search(r"\bipc\b", normalized) or "indian penal code" in normalized:
            filtered = [
                item for item in prioritized
                if "ipc" in f"{item.get('title', '')} {item.get('citation', '')} {item.get('text', '')}".lower()
                or "indian penal code" in f"{item.get('title', '')} {item.get('citation', '')} {item.get('text', '')}".lower()
            ]
            if filtered:
                prioritized = filtered
        if re.search(r"\bcrpc\b", normalized) or "code of criminal procedure" in normalized:
            filtered = [
                item for item in prioritized
                if "crpc" in f"{item.get('title', '')} {item.get('citation', '')} {item.get('text', '')}".lower()
                or "code of criminal procedure" in f"{item.get('title', '')} {item.get('citation', '')} {item.get('text', '')}".lower()
            ]
            if filtered:
                prioritized = filtered
        if re.search(r"\bdpdp\b", normalized) or "digital personal data protection" in normalized:
            filtered = [
                item for item in prioritized
                if "dpdp" in f"{item.get('title', '')} {item.get('citation', '')} {item.get('text', '')}".lower()
                or "digital personal data protection" in f"{item.get('title', '')} {item.get('citation', '')} {item.get('text', '')}".lower()
            ]
            if filtered:
                prioritized = filtered
        return prioritized

    def _synthesize_chat_answer(
        self,
        question: str,
        sources: list[SourceDocument],
        history: list | None = None,
    ) -> dict:
        if not sources:
            return {
                "answer": "I could not retrieve a matching legal passage for that question from the current corpus.",
                "reasoning": "NyayaSetu is running without a generation model, so the reply must stay tied to retrieved legal material already indexed.",
            }

        recent_context = self._history_context_snippet(history or [])
        lead = sources[0]
        supporting = sources[1:3]
        citations = ", ".join(dict.fromkeys(source.citation for source in sources[:3]))
        explanation = self._compose_question_specific_summary(question, sources)
        support_lines = [
            f"- {source.reference_path or source.citation}: {self._supporting_summary(question, source)}"
            for source in supporting
        ]
        next_steps = self._suggest_question_specific_steps(question, sources)
        retrieval_modes = ", ".join(sorted(dict.fromkeys(source.retrieval_mode or "semantic" for source in sources[:3])))
        answer_parts = [
            f"Short answer: {explanation}",
            f"Most relevant authority: {lead.citation}.",
        ]
        if recent_context:
            answer_parts.append(f"Conversation context used: {recent_context}")
        answer_parts.append("Structured reference path:\n" + "\n".join(f"- {source.reference_path or source.citation}" for source in sources[:3]))
        if support_lines:
            answer_parts.append("Supporting material:\n" + "\n".join(support_lines))
        if next_steps:
            answer_parts.append("Practical next steps:\n" + "\n".join(f"- {step}" for step in next_steps))
        answer_parts.append(f"Grounded citations: {citations}.")
        reasoning = (
            "NyayaSetu used hybrid retrieval for this answer. "
            f"It fused {retrieval_modes} evidence, prioritized {citations}, and converted the retrieved excerpts into plain-language guidance."
        )
        return {"answer": "\n\n".join(answer_parts), "reasoning": reasoning}

    def _build_contextual_question(self, payload: ChatRequest) -> str:
        question = payload.question.strip()
        prior_user_turns = [message.content.strip() for message in payload.history if message.role == "user" and message.content.strip()]
        if not prior_user_turns:
            return question
        if len(question.split()) <= 8 or re.search(r"\b(this|that|it|they|same|above|those|these|section)\b", question.lower()):
            return f"{prior_user_turns[-1]} {question}".strip()
        return question

    def _format_history_for_prompt(self, history: list) -> str:
        if not history:
            return ""
        recent = history[-4:]
        return "\n".join(f"{message.role.title()}: {message.content.strip()}" for message in recent if message.content.strip())

    def _history_context_snippet(self, history: list) -> str:
        if not history:
            return ""
        user_messages = [message.content.strip() for message in history if getattr(message, "role", "") == "user" and message.content.strip()]
        if not user_messages:
            return ""
        return user_messages[-1][:220]

    def _compose_question_specific_summary(self, question: str, sources: list[SourceDocument]) -> str:
        normalized = question.lower()
        if "arrest" in normalized and any(keyword in normalized for keyword in ("right", "rights", "bail", "advocate", "lawyer")):
            return self._summarize_arrest_rights(sources)
        if "fir" in normalized and any(keyword in normalized for keyword in ("cognizable", "register", "registration", "refuse", "refusal")):
            return self._summarize_fir_registration(sources)
        if ("section 187" in normalized or re.search(r"\b187\b", normalized)) and ("bnss" in normalized or "bharatiya nagarik suraksha sanhita" in normalized):
            return self._summarize_bnss_section_187(sources)
        if "punishment" in normalized and "cheating" in normalized:
            return self._summarize_cheating_punishment(sources)
        if any(keyword in normalized for keyword in ("online payment", "payment fraud", "otp", "bank fraud", "cyber fraud")) or (
            any(keyword in normalized for keyword in ("online", "payment", "otp", "bank", "cyber"))
            and any(keyword in normalized for keyword in ("fraud", "cheating", "scam"))
        ):
            return self._summarize_online_payment_fraud(sources)
        return self._plain_language_summary(sources[0])

    def _summarize_arrest_rights(self, sources: list[SourceDocument]) -> str:
        details: list[str] = []
        if self._find_source(sources, "grounds of arrest") or self._find_source(sources, "Section 47"):
            details.append("you should be told the grounds of arrest")
        if self._find_source(sources, "right to bail") or self._find_source(sources, "Section 478"):
            details.append("in bailable cases, you should be informed about bail")
        if self._find_source(sources, "advocate of his choice") or self._find_source(sources, "Section 38"):
            details.append("you can meet an advocate of your choice during interrogation")
        if not details:
            return self._plain_language_summary(sources[0])
        return "If you are arrested, " + self._join_human_list(details) + "."

    def _summarize_fir_registration(self, sources: list[SourceDocument]) -> str:
        if self._find_source(sources, "Section 173"):
            return (
                "For a cognizable offence, the police are expected to record the information and give the informant a free copy of what was recorded. "
                "A limited preliminary enquiry may happen in some cases, but that is not the same as refusing the complaint altogether."
            )
        return self._plain_language_summary(sources[0])

    def _summarize_bnss_section_187(self, sources: list[SourceDocument]) -> str:
        excerpts = [self._normalized_excerpt(source).lower() for source in sources[:3]]
        if any("magistrate" in excerpt for excerpt in excerpts) and any(
            keyword in excerpt for excerpt in excerpts for keyword in ("detention", "custody", "fifteen days")
        ):
            return (
                "Section 187 BNSS is about detention during investigation and the Magistrate's control over further custody. "
                "In simple terms, the police cannot keep a person in custody indefinitely on their own, and the law sets judicial checks and time limits."
            )
        return self._plain_language_summary(sources[0])

    def _summarize_cheating_punishment(self, sources: list[SourceDocument]) -> str:
        available = {source.citation: self._normalized_excerpt(source) for source in sources[:4]}
        if any("section 318(2)" in citation.lower() for citation in available):
            return (
                "Under BNS Section 318, simple cheating can lead to up to 3 years' imprisonment, fine, or both. "
                "More serious forms can go up to 5 years or 7 years depending on the wrongful-loss or property-delivery facts."
            )
        return self._plain_language_summary(sources[0])

    def _summarize_online_payment_fraud(self, sources: list[SourceDocument]) -> str:
        if self._find_source(sources, "Section 66D") or self._find_source(sources, "computer resource"):
            return (
                "Online payment fraud can overlap with cyber-cheating and cheating provisions. "
                "The immediate priorities are to secure the bank or payment account, preserve the transaction trail, and report the matter quickly."
            )
        return (
            "After an online payment fraud, act quickly to secure the account, preserve transaction records, and report the incident. "
            "The legal position depends on the exact cheating or cyber-fraud facts shown by the evidence."
        )

    def _supporting_summary(self, question: str, source: SourceDocument) -> str:
        normalized = question.lower()
        excerpt = self._normalized_excerpt(source)
        if "punishment" in normalized and "cheating" in normalized and "shall be punished" in excerpt:
            return self._convert_punishment_excerpt(excerpt)
        if "section 187" in normalized and "detention" in excerpt:
            return "This part of Section 187 explains the Magistrate's role in approving further detention and setting custody limits."
        if any(keyword in normalized for keyword in ("arrest", "rights", "bail", "advocate")):
            if "grounds of arrest" in excerpt:
                return "This source says the arrested person should be told the grounds of arrest."
            if "right to bail" in excerpt or "released on bail" in excerpt:
                return "This source covers the right to bail in bailable cases."
            if "advocate of his choice" in excerpt:
                return "This source says the arrested person can meet an advocate of choice during interrogation."
        if "cognizable offence" in excerpt and "copy" in excerpt:
            return "This source says the informant or victim should get a free copy of the recorded information."
        return self._plain_language_summary(source)

    def _plain_language_summary(self, source: SourceDocument) -> str:
        excerpt = self._normalized_excerpt(source)
        heading_match = re.match(r"^\d+[A-Za-z()/-]*\.\s*([^.-]{4,140})\s*[.-]+\s*(.+)$", excerpt)
        if heading_match:
            heading = heading_match.group(1).strip(" .")
            body = heading_match.group(2).strip()
            if "shall be punished" in body:
                return f"{heading} - {self._convert_punishment_excerpt(body)}"
            sentence = re.split(r"(?<=[.!?])\s+", body)[0].strip()
            if sentence:
                return f"{heading} means {sentence[:220]}"
        if excerpt.startswith("(") and "shall be punished" in excerpt:
            return self._convert_punishment_excerpt(excerpt)
        if excerpt.startswith("(") and "shall be entitled to" in excerpt:
            sentence = re.split(r"(?<=[.!?])\s+", excerpt)[0].strip()
            return sentence.replace("shall be entitled to", "is entitled to")
        sentence = re.split(r"(?<=[.!?])\s+", excerpt)[0].strip()
        if sentence:
            return sentence[:220]
        return excerpt[:220]

    def _convert_punishment_excerpt(self, excerpt: str) -> str:
        cleaned = re.sub(r"^\([0-9A-Za-z]+\)\s*", "", excerpt).strip()
        cleaned = cleaned.replace("Whoever", "").strip(" .")
        term_match = re.search(r"term which may extend to ([a-z0-9 -]+?years?)", cleaned, flags=re.IGNORECASE)
        fine = "fine" in cleaned.lower()
        if term_match:
            term = term_match.group(1).strip()
            if fine:
                return f"This provision allows imprisonment for up to {term}, along with fine."
            return f"This provision allows imprisonment for up to {term}."
        return cleaned[:220]

    def _grounding_fragments(self, source: SourceDocument) -> list[str]:
        fragments: list[str] = []
        fragments.append(source.title.lower())
        fragments.extend(
            fragment.lower()
            for fragment in re.split(r"(?<=[.!?])\s+", source.excerpt)
            if fragment.strip()
        )
        return [fragment[:180] for fragment in fragments if len(fragment.strip()) >= 12]

    def _suggest_question_specific_steps(self, question: str, sources: list[SourceDocument]) -> list[str]:
        _ = sources
        normalized = question.lower()
        if any(keyword in normalized for keyword in ["fir", "complaint", "police"]):
            return [
                "Prepare a clear chronology with dates, times, location, and names.",
                "Attach original screenshots, recordings, IDs, or other primary evidence.",
                "Ask for a receiving copy or FIR number after submission.",
            ]
        if any(keyword in normalized for keyword in ["cyber", "otp", "fraud", "online"]):
            return [
                "Preserve bank alerts, transaction IDs, device details, and call records.",
                "Document the exact timeline of the fraud before memories fade.",
                "Speak with a lawyer if recovery, freezing, or police escalation is urgent.",
            ]
        if any(keyword in normalized for keyword in ["tenant", "landlord", "deposit", "property"]):
            return [
                "Keep the rent agreement, payment proof, and written communication in one file.",
                "Send a written demand before moving to a formal notice where appropriate.",
                "Consult a property lawyer before filing if facts are disputed.",
            ]
        if any(keyword in normalized for keyword in ["arrest", "detention", "bail"]):
            return [
                "Record the time, place, and grounds communicated for the arrest or detention.",
                "Inform a relative or trusted person immediately and request legal assistance.",
                "Preserve any paperwork, medical records, or witness details linked to the incident.",
            ]
        return [
            "Preserve the original documents and communications linked to the issue.",
            "Write down the chronology in plain language before taking the next legal step.",
            "Get a lawyer to review the facts if the matter could lead to police or court action.",
        ]

    def _fallback_answer(self, sources: list[SourceDocument]) -> str:
        if not sources:
            return "No matching legal materials were retrieved. Rephrase the question or expand the legal corpus."
        lead = sources[0]
        return (
            f"The strongest grounded authority retrieved for this question is {lead.citation}. "
            "Review that source carefully and have a qualified lawyer check how it applies to your facts."
        )

    def _normalized_excerpt(self, source: SourceDocument) -> str:
        replacements = {
            "\u2014": " - ",
            "\u2013": " - ",
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u00a0": " ",
        }
        cleaned = source.excerpt
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)
        return re.sub(r"\s+", " ", cleaned).strip()

    def _find_source(self, sources: list[SourceDocument], needle: str) -> SourceDocument | None:
        lowered = needle.lower()
        for source in sources:
            haystack = f"{source.citation} {source.reference_path or ''} {source.excerpt}".lower()
            if lowered in haystack:
                return source
        return None

    def _dedupe_hits(self, hits: list[dict]) -> list[dict]:
        seen: set[str] = set()
        deduped: list[dict] = []
        for item in hits:
            key = str(item.get("citation") or item.get("reference_path") or item.get("title"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _join_human_list(self, parts: list[str]) -> str:
        unique_parts = list(dict.fromkeys(part.strip() for part in parts if part.strip()))
        if not unique_parts:
            return ""
        if len(unique_parts) == 1:
            return unique_parts[0]
        if len(unique_parts) == 2:
            return f"{unique_parts[0]} and {unique_parts[1]}"
        return ", ".join(unique_parts[:-1]) + f", and {unique_parts[-1]}"

    def _fallback_reasoning(self, sources: list[SourceDocument]) -> str:
        return "The incident pattern overlaps with the retrieved provisions, subject to factual verification and procedural requirements."

    def _suggest_evidence(self, current_evidence: list[str]) -> list[str]:
        baseline = ["Original screenshots or communications", "Witness statements", "Identity and address proof"]
        if not current_evidence:
            return baseline
        return current_evidence + [item for item in baseline if item not in current_evidence]

    def _infer_case_type(self, description: str, laws: list[str]) -> str:
        haystack = f"{description} {' '.join(laws)}".lower()
        criminal_terms = (
            "fir",
            "police",
            "arrest",
            "bail",
            "theft",
            "fraud",
            "cheating",
            "assault",
            "harassment",
            "ipc",
            "bns",
            "bnss",
            "crpc",
            "seller took money",
            "never delivered",
            "payment fraud",
        )
        return "criminal" if any(term in haystack for term in criminal_terms) else "civil"

    def _boost_legal_query(self, query: str) -> str:
        normalized = query.lower()
        expansions: list[str] = []
        if (
            any(keyword in normalized for keyword in ("money", "payment", "seller", "buyer", "delivery"))
            and any(keyword in normalized for keyword in ("never delivered", "not delivered", "stopped responding", "dishonest", "fraud", "cheating", "scam"))
        ):
            expansions.append("cheating fraud property delivery IPC section 420 BNS section 318 online payment fraud")
        if any(keyword in normalized for keyword in ("salary", "wages", "employer", "employment", "offer letter", "salary slip")):
            expansions.append("employment salary dues written notice contract unpaid wages documentary proof")
        if any(keyword in normalized for keyword in ("personal data", "privacy", "consent", "data breach", "data fiduciary", "dpdp")):
            expansions.append("DPDP Act 2023 personal data consent data fiduciary grievance redressal")
        if "fir" in normalized and any(keyword in normalized for keyword in ("register", "refuse", "cognizable", "complaint")):
            expansions.append("CrPC section 154 BNSS section 173 FIR registration cognizable offence")
        return " ".join([query, *expansions]).strip()

    def _infer_parties(self, description: str) -> list[str]:
        lowered = description.lower()
        inferred: list[str] = []
        party_map = {
            "complainant": ("complainant", "victim", "informant", "tenant", "buyer", "employee", "wife", "husband"),
            "respondent": ("accused", "landlord", "seller", "employer", "company", "husband", "wife"),
        }
        for label, keywords in party_map.items():
            if any(keyword in lowered for keyword in keywords):
                inferred.append(label.title())
        return inferred or ["Complainant", "Opposite Party"]

    def _extract_case_facts(self, description: str, location: str | None, incident_date: str | None) -> list[str]:
        facts = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", description.strip()) if sentence.strip()]
        selected = facts[:3]
        if incident_date:
            selected.append(f"Incident date mentioned: {incident_date}.")
        if location:
            selected.append(f"Incident location mentioned: {location}.")
        return selected or [description[:280]]

    def _infer_legal_issues(self, description: str, sources: list[SourceDocument]) -> list[str]:
        lowered = description.lower()
        issues: list[str] = []
        if any(keyword in lowered for keyword in ("fraud", "cheating", "scam", "dishonest")):
            issues.append("Possible cheating or deception-based criminal liability.")
        if any(keyword in lowered for keyword in ("theft", "snatch", "stolen", "robbed")):
            issues.append("Possible theft or dishonest misappropriation issues.")
        if any(keyword in lowered for keyword in ("privacy", "personal data", "data breach", "consent")):
            issues.append("Possible personal data processing and privacy compliance issues.")
        if any(keyword in lowered for keyword in ("notice", "agreement", "payment", "rent", "deposit")):
            issues.append("Contractual or notice-related obligations may need review.")
        if not issues and sources:
            issues.append(f"Potential applicability of {sources[0].citation}.")
        return issues or ["Factual clarification is needed before narrowing the core legal issues."]

    def _derive_case_strengths(self, description: str, evidence: list[str], sources: list[SourceDocument]) -> list[str]:
        strengths: list[str] = []
        if len(description.split()) >= 35:
            strengths.append("The narrative contains enough detail for initial legal mapping.")
        if evidence:
            strengths.append("The matter already includes identified evidence sources.")
        if any("official" in (source.source_url or "") or "indiacode.nic.in" in (source.source_url or "") for source in sources):
            strengths.append("The analysis is grounded in official statutory material.")
        return strengths or ["A preliminary legal pathway can be identified from the facts already provided."]

    def _derive_case_weaknesses(self, description: str, evidence: list[str], location: str | None) -> list[str]:
        weaknesses: list[str] = []
        if len(description.split()) < 25:
            weaknesses.append("The factual narrative is still short and may omit important legal details.")
        if not evidence:
            weaknesses.append("No direct evidence has been described yet.")
        if not location:
            weaknesses.append("Location is missing, which can affect jurisdiction and verification.")
        return weaknesses

    def _derive_missing_case_elements(self, payload: CaseAnalysisRequest) -> list[str]:
        missing: list[str] = []
        if not payload.incident_date:
            missing.append("Exact incident date or date range.")
        if not payload.location:
            missing.append("Incident location or police station jurisdiction.")
        if not payload.people_involved:
            missing.append("Names or roles of the main parties involved.")
        if not payload.evidence:
            missing.append("Primary evidence such as screenshots, receipts, messages, CCTV, or witness details.")
        return missing

    def _suggest_case_actions(self, case_type: str, evidence: list[str]) -> list[str]:
        actions = [
            "Prepare a clear chronology of events with dates, times, and names.",
            "Preserve original messages, screenshots, documents, and device metadata.",
            "Consult a lawyer before filing or responding to any formal legal process.",
        ]
        if case_type == "criminal":
            actions.insert(1, "Identify the correct police station and keep a ready complaint draft.")
        if not evidence:
            actions.insert(0, "Collect direct proof before escalation where possible.")
        return actions

    def _infer_possible_outcomes(self, case_type: str, sources: list[SourceDocument]) -> list[str]:
        if case_type == "criminal":
            return [
                "Police complaint or FIR registration may follow if cognizable ingredients are made out.",
                "Further investigation, witness examination, and evidence preservation will affect the final charges.",
                "The final outcome will depend on proof quality, procedural compliance, and judicial assessment.",
            ]
        return [
            "A legal notice, negotiated settlement, or civil filing may be considered depending on the evidence.",
            "Relief may depend on contract terms, payment records, and proof of breach or loss.",
        ]

    def _summarize_possible_punishment(self, sources: list[SourceDocument]) -> str:
        punishment_lines = [
            self._plain_language_summary(source)
            for source in sources
            if any(keyword in source.excerpt.lower() for keyword in ("punished", "imprisonment", "fine"))
        ]
        if punishment_lines:
            return "; ".join(dict.fromkeys(punishment_lines[:3]))
        return "Possible punishment depends on the final sections invoked, proof produced, and judicial findings."

    def _compose_case_analysis_summary(
        self,
        case_type: str,
        laws: list[str],
        strengths: list[str],
        weaknesses: list[str],
        missing_elements: list[str],
    ) -> str:
        law_hint = laws[0] if laws else "the retrieved legal materials"
        lead_strength = (strengths[0] if strengths else "limited").rstrip(".")
        lead_weakness = (weaknesses[0] if weaknesses else "the need for factual verification").rstrip(".")
        lead_missing = (missing_elements[0] if missing_elements else "further corroboration").rstrip(".")
        if case_type == "criminal":
            return (
                f"This appears to be a criminal matter with initial overlap against {law_hint}. "
                f"The current strengths are {lead_strength.lower()}. "
                f"The main risk is {lead_weakness.lower()}, "
                f"and the highest-priority missing item is {lead_missing.lower()}."
            )
        return (
            f"This appears to be a civil or mixed dispute that should be assessed against {law_hint}. "
            f"The matter is presently strongest where {lead_strength.lower()}, "
            f"but weaker where {lead_weakness.lower()}."
        )

    def _estimate_evidence_items(self, description: str) -> int:
        matches = re.findall(
            r"\b(screenshot|invoice|recording|photo|video|cctv|document|statement|receipt|chat|email|emails|bank record|salary slip|salary slips|offer letter|notice)\b",
            description,
            flags=re.IGNORECASE,
        )
        return min(len(set(match.lower() for match in matches)), 4)

    def _estimate_witness_count(self, description: str) -> int:
        if re.search(r"\b(witness|eyewitness|seen by|in front of others|independent witness)\b", description, flags=re.IGNORECASE):
            return 1
        return 0

    def _has_documentary_support(self, description: str) -> bool:
        return bool(
            re.search(
                r"\b(document|agreement|invoice|receipt|statement|email|emails|notice|bank record|medical report|salary slip|salary slips|offer letter)\b",
                description,
                flags=re.IGNORECASE,
            )
        )

    def _compose_case_strength_summary(
        self,
        score: int,
        label: str,
        strengths: list[str],
        weaknesses: list[str],
        missing_elements: list[str],
        suggested_sections: list[str],
        has_similar_cases: bool,
    ) -> str:
        lead_strength = (strengths[0] if strengths else "limited baseline legal alignment").rstrip(".")
        lead_weakness = (weaknesses[0] if weaknesses else "uncertainty in the available facts").rstrip(".")
        lead_missing = (missing_elements[0] if missing_elements else "additional corroboration").rstrip(".")
        precedent_line = (
            "Verified precedent support was found in the indexed case-law dataset."
            if has_similar_cases
            else "The current deployment still needs a dedicated court-judgment corpus for verified precedent matching."
        )
        return (
            f"The case scores {score}/100 and is presently classified as {label}. "
            f"The strongest factor is {lead_strength.lower()}. "
            f"The main risk is {lead_weakness.lower()}. "
            f"The top missing item is {lead_missing.lower()}. "
            f"The most relevant sections currently retrieved are {', '.join(suggested_sections[:3]) if suggested_sections else 'not yet clear'}. "
            f"{precedent_line}"
        )

    def _extract_verified_case_references(self, sources: list[SourceDocument]) -> list[SimilarCaseReference]:
        cases: list[SimilarCaseReference] = []
        for source in sources:
            if source.source_type not in {"judgment", "case_law", "precedent"}:
                continue
            metadata = source.metadata or {}
            court = metadata.get("court") or (
                "Supreme Court of India"
                if "supreme-court" in (source.source_url or "") or "sci.gov.in" in (source.source_url or "")
                else "High Court of India"
            )
            verdict = metadata.get("verdict") or self._plain_language_summary(source)
            parties = metadata.get("parties") or metadata.get("case_title") or source.title
            comparison_reason = "; ".join(
                part
                for part in [
                    f"Decision date: {metadata.get('decision_date')}" if metadata.get("decision_date") else "",
                    f"Case no.: {metadata.get('case_number')}" if metadata.get("case_number") else "",
                    f"Dataset: {metadata.get('dataset')}" if metadata.get("dataset") else "",
                    source.reference_path or source.citation,
                ]
                if part
            )
            cases.append(
                SimilarCaseReference(
                    case_title=metadata.get("case_title") or source.title,
                    court=court,
                    verdict=verdict,
                    source_link=source.source_url or "",
                    similarity_score=f"{round(source.score * 100, 1)}%",
                    parties=parties,
                    fir_summary=source.excerpt[:220],
                    charges=source.citation,
                    comparison_reasoning=comparison_reason,
                    relevance=source.excerpt[:220],
                    relevance_reason=comparison_reason,
                )
            )
        return cases[:5]

    def _build_case_search_results(self, hits: list[SourceDocument]) -> list[ResearchCaseResult]:
        results: list[ResearchCaseResult] = []
        for source in hits:
            if source.source_type not in {"judgment", "case_law", "precedent"}:
                continue
            metadata = source.metadata or {}
            court = metadata.get("court") or (
                "Supreme Court of India"
                if "supreme-court" in (source.source_url or "") or "sci.gov.in" in (source.source_url or "")
                else "High Court of India"
            )
            verdict = metadata.get("verdict") or self._plain_language_summary(source)
            parties = metadata.get("parties") or metadata.get("case_title") or source.title
            comparison_reason = "; ".join(
                part
                for part in [
                    f"Decision date: {metadata.get('decision_date')}" if metadata.get("decision_date") else "",
                    f"Case no.: {metadata.get('case_number')}" if metadata.get("case_number") else "",
                    f"Dataset: {metadata.get('dataset')}" if metadata.get("dataset") else "",
                    source.reference_path or source.citation,
                ]
                if part
            )
            results.append(
                ResearchCaseResult(
                    case_title=metadata.get("case_title") or source.title,
                    court=court,
                    similarity_score=f"{round(source.score * 100, 1)}%",
                    parties=parties,
                    fir_summary=source.excerpt[:220],
                    charges=source.citation,
                    verdict=verdict,
                    source_link=source.source_url or "",
                    comparison_reasoning=comparison_reason,
                )
            )
        return results[:10]

    def _analyze_fir_intelligence(self, query: str) -> ResearchFIRAnalysis:
        sources = self._retrieve_sources(query, top_k=6)
        suggested_sections = [source.citation for source in sources[:5]]
        missing_items = self._detect_missing_fir_elements(query)
        similar_firs = self._find_similar_fir_records(query, suggested_sections)
        improved_draft = self._render_improved_fir_draft(query, suggested_sections, missing_items)
        risk_parts = [
            "FIR structure validation completed against the available narrative.",
            f"Suggested sections: {', '.join(suggested_sections[:4]) if suggested_sections else 'insufficient grounded section match'}.",
        ]
        if missing_items:
            risk_parts.append(f"Missing legal elements: {', '.join(missing_items)}.")
        if similar_firs:
            risk_parts.append(
                "Past similar FIR patterns were found in NyayaSetu records: "
                + "; ".join(similar_firs[:3])
                + "."
            )
        else:
            risk_parts.append("No close prior FIR record match was found in the current database.")
        return ResearchFIRAnalysis(
            improved_draft=improved_draft,
            suggested_sections=", ".join(suggested_sections),
            risk_analysis=" ".join(risk_parts).strip(),
        )

    def _detect_missing_fir_elements(self, query: str) -> list[str]:
        lowered = query.lower()
        missing: list[str] = []
        checks = {
            "incident date": r"\b(today|yesterday|last night|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
            "incident location": r"\b(at|near|in)\s+[a-z]",
            "accused details": r"\b(accused|suspect|person|bike|vehicle|registration|mobile number)\b",
            "witness information": r"\b(witness|seen by|in front of)\b",
            "evidence information": r"\b(cctv|screenshot|photo|video|receipt|recording|document)\b",
        }
        for label, pattern in checks.items():
            if not re.search(pattern, lowered, flags=re.IGNORECASE):
                missing.append(label)
        return missing

    def _find_similar_fir_records(self, query: str, suggested_sections: list[str]) -> list[str]:
        session = SessionLocal()
        try:
            query_tokens = {
                token.lower()
                for token in re.findall(r"[a-z0-9]{4,}", query.lower())
                if token.lower() not in {"section", "police", "complaint", "report"}
            }
            rows = session.query(FIRRecord).order_by(FIRRecord.last_edited_at.desc()).limit(40).all()
            ranked: list[tuple[int, str]] = []
            for row in rows:
                try:
                    extracted = json.loads(row.extracted_payload)
                except Exception:
                    extracted = {}
                incident_description = str(extracted.get("incident_description", ""))
                row_tokens = set(re.findall(r"[a-z0-9]{4,}", incident_description.lower()))
                overlap = len(query_tokens & row_tokens)
                try:
                    stored_sections = [item.get("citation", "") for item in json.loads(row.suggested_sections)]
                except Exception:
                    stored_sections = []
                shared_sections = len(set(suggested_sections) & set(stored_sections))
                if overlap == 0 and shared_sections == 0:
                    continue
                label = incident_description[:120] or row.id
                ranked.append((shared_sections * 4 + overlap, label))
            ranked.sort(key=lambda item: item[0], reverse=True)
            return [label for _, label in ranked[:5]]
        finally:
            session.close()

    def _render_improved_fir_draft(self, query: str, suggested_sections: list[str], missing_items: list[str]) -> str:
        sections_block = ", ".join(suggested_sections[:4]) if suggested_sections else "[section mapping pending]"
        missing_block = (
            "\nMissing information to add: " + ", ".join(missing_items) + "."
            if missing_items
            else ""
        )
        return dedent(
            f"""
            To,
            The Station House Officer

            Subject: Request for registration of complaint / FIR

            I respectfully submit that the following incident requires legal action:
            {query.strip()}

            Tentatively relevant sections:
            {sections_block}

            I request prompt registration, preservation of evidence, and further investigation as per law.{missing_block}
            """
        ).strip()

    def _extract_clauses(self, text: str) -> list[ContractClause]:
        clause_map = {
            "Payment": ("payment", "fee", "invoice", "consideration"),
            "Termination": ("termination", "terminate", "exit"),
            "Liability": ("liability", "liable", "damages"),
            "Indemnity": ("indemnity", "indemnify", "hold harmless"),
            "Confidentiality": ("confidential", "non-disclosure", "nda"),
            "Dispute Resolution": ("arbitration", "dispute", "jurisdiction", "governing law"),
            "IP": ("intellectual property", "ip", "copyright", "license"),
            "Force Majeure": ("force majeure", "act of god", "unforeseen event"),
        }
        lowered = text.lower()
        clauses: list[ContractClause] = []
        for clause_name, keywords in clause_map.items():
            excerpt = self._contract_clause_excerpt(text, keywords)
            if not excerpt:
                continue
            risk_level, issue, suggestion = self._contract_clause_risk(clause_name, excerpt)
            improved_clause = self._contract_clause_rewrite(clause_name, excerpt, risk_level, suggestion)
            clauses.append(
                ContractClause(
                    clause_name=clause_name,
                    summary=excerpt[:260],
                    risk_level=risk_level,
                    issue=issue,
                    suggestion=suggestion,
                    improved_clause=improved_clause,
                )
            )
        if not clauses:
            fallback_excerpt = text[:400].strip() or "No contract text could be extracted."
            clauses.append(
                ContractClause(
                    clause_name="General Terms",
                    summary=fallback_excerpt,
                    risk_level="Medium",
                    issue="The contract does not show clearly separable clause headings.",
                    suggestion="Structure the contract into labelled clauses for easier review and negotiation.",
                    improved_clause="Add clearly headed clauses for payment, liability, confidentiality, termination, and dispute resolution.",
                )
            )
        if "without notice" in lowered and not any(clause.clause_name == "Termination" for clause in clauses):
            clauses.append(
                ContractClause(
                    clause_name="Termination",
                    summary="Termination appears to be exercisable without notice.",
                    risk_level="High",
                    issue="Immediate termination without notice can create one-sided risk.",
                    suggestion="Add prior written notice, cure period, and refund/settlement mechanics.",
                    improved_clause="Either party may terminate this agreement by giving 30 days' written notice, subject to a 15-day cure period for remediable breaches.",
                )
            )
        return clauses

    def _missing_contract_clauses(self, text: str) -> list[str]:
        lowered = text.lower()
        expected = {
            "payment": "Payment",
            "termination": "Termination",
            "liability": "Liability",
            "indemnity": "Indemnity",
            "confidentiality": "Confidentiality",
            "governing law": "Governing Law",
            "dispute resolution": "Dispute Resolution",
            "intellectual property": "IP",
            "force majeure": "Force Majeure",
        }
        return [label for key, label in expected.items() if key not in lowered]

    def _detect_contract_type(self, text: str) -> str:
        lowered = text.lower()
        patterns = {
            "Employment Contract": ("employment", "employee", "employer", "salary"),
            "Rental Agreement": ("rent", "tenant", "landlord", "lease"),
            "Service Agreement": ("service agreement", "services", "service provider", "scope of work"),
            "Non-Disclosure Agreement": ("confidential", "non-disclosure", "nda"),
            "Sale Agreement": ("sale", "buyer", "seller", "goods"),
            "Consultancy Agreement": ("consultant", "consulting", "professional fee"),
        }
        for contract_type, keywords in patterns.items():
            if any(keyword in lowered for keyword in keywords):
                return contract_type
        return "General Contract"

    def _extract_contract_parties(self, text: str) -> list[str]:
        between_match = re.search(r"between\s+(.+?)\s+and\s+(.+?)(?:,|\n|$)", text, flags=re.IGNORECASE | re.DOTALL)
        if between_match:
            parties = [between_match.group(1).strip(" ,."), between_match.group(2).strip(" ,.")]
            return [party[:120] for party in parties if party]
        candidates = re.findall(r"\b[A-Z][A-Za-z&., ]{2,40}\b", text[:500])
        filtered = [candidate.strip(" ,.") for candidate in candidates if len(candidate.strip()) >= 3]
        return list(dict.fromkeys(filtered[:4]))

    def _contract_clause_excerpt(self, text: str, keywords: tuple[str, ...]) -> str:
        lowered = text.lower()
        for keyword in keywords:
            index = lowered.find(keyword)
            if index >= 0:
                start = max(0, index - 90)
                end = min(len(text), index + 250)
                return re.sub(r"\s+", " ", text[start:end]).strip()
        return ""

    def _contract_clause_risk(self, clause_name: str, excerpt: str) -> tuple[str, str, str]:
        lowered = excerpt.lower()
        if clause_name == "Payment":
            if "sole discretion" in lowered or "non-refundable" in lowered:
                return "High", "Payment terms appear one-sided or insufficiently conditioned.", "Define milestones, invoice timelines, refund conditions, and late-fee limits."
            return "Low", "Payment clause is present with no immediate red-flag language.", "Confirm due dates, invoice requirements, and tax treatment."
        if clause_name == "Termination":
            if "without notice" in lowered or "immediate" in lowered:
                return "High", "Termination may be exercisable without adequate notice or cure rights.", "Add written notice, cure periods, and post-termination obligations."
            return "Medium", "Termination clause exists but should still be checked for notice and cure structure.", "Ensure notice period, breach cure, and settlement mechanics are clearly stated."
        if clause_name in {"Liability", "Indemnity"}:
            if "unlimited" in lowered or ("indemn" in lowered and "cap" not in lowered):
                return "High", "Exposure may be uncapped or commercially unbalanced.", "Introduce liability caps, exclusions, and narrowly tailored indemnity triggers."
            return "Medium", "Liability allocation exists but may need balancing.", "Check whether the clause has reasonable caps, carve-outs, and reciprocal protection."
        if clause_name == "Confidentiality":
            if "perpetual" in lowered and "exception" not in lowered:
                return "Medium", "Confidentiality obligations may be broad without clear exceptions.", "Define confidential information, exclusions, and survival period."
            return "Low", "Confidentiality coverage is visible.", "Confirm exceptions, duration, and return/deletion obligations."
        if clause_name == "Dispute Resolution":
            if "exclusive jurisdiction" in lowered and "arbitration" not in lowered:
                return "Medium", "Forum selection is present but dispute mechanics may be incomplete.", "Clarify negotiation step, governing law, seat, and procedure."
            return "Low", "Dispute resolution clause appears present.", "Confirm governing law, forum, and escalation path."
        if clause_name == "IP":
            if "all rights" in lowered and "license" not in lowered:
                return "High", "IP allocation may be overbroad or ambiguous.", "Specify ownership, license scope, derivative works, and pre-existing IP."
            return "Medium", "IP language exists but should be scoped carefully.", "Separate background IP from deliverable ownership."
        if clause_name == "Force Majeure":
            return "Low", "Force majeure language is present.", "Check notice obligations and mitigation duty."
        return "Medium", "Clause requires closer legal review.", "Clarify obligations, trigger conditions, and remedies."

    def _contract_clause_rewrite(self, clause_name: str, excerpt: str, risk_level: str, suggestion: str) -> str:
        if risk_level != "High":
            return ""
        templates = {
            "Termination": "Either party may terminate this agreement for material breach upon 30 days' written notice if the breach remains uncured during that period.",
            "Liability": "Neither party shall be liable for indirect or consequential loss, and aggregate liability shall not exceed the fees paid under this agreement, except for fraud, wilful misconduct, confidentiality breach, or third-party IP claims.",
            "Indemnity": "Each party shall indemnify the other only for third-party claims arising from its breach, negligence, or wilful misconduct, subject to prompt notice and reasonable defence control.",
            "Payment": "Invoices shall be raised against agreed milestones and paid within 15 days of receipt, with any good-faith dispute notified in writing within 7 days.",
            "IP": "Each party retains ownership of its pre-existing intellectual property. Deliverables created specifically under this agreement shall vest as expressly stated, while any license granted shall be limited, non-exclusive, and purpose-specific.",
        }
        return templates.get(clause_name, f"Suggested rewrite: {suggestion} Current excerpt: {excerpt[:140]}")

    def _score_contract_risk(self, clauses: list[ContractClause], missing: list[str]) -> int:
        counter = Counter(clause.risk_level for clause in clauses)
        score = counter.get("High", 0) * 22 + counter.get("Medium", 0) * 10 + len(missing) * 5
        return max(0, min(100, score))

    def _contract_negotiation_insights(self, clauses: list[ContractClause], missing: list[str]) -> list[str]:
        insights = [
            clause.suggestion
            for clause in clauses
            if clause.risk_level in {"High", "Medium"}
        ]
        if missing:
            insights.append("Add missing commercial boilerplate before execution: " + ", ".join(missing[:4]) + ".")
        if not insights:
            insights.append("Negotiate only after validating governing law, payment cycle, and liability allocation.")
        return list(dict.fromkeys(insights))

    def _extract_entities(self, text: str) -> list[EvidenceEntity]:
        entities: list[EvidenceEntity] = []
        for date in re.findall(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", text):
            entities.append(EvidenceEntity(label="date", value=date))
        for email in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text):
            entities.append(EvidenceEntity(label="email", value=email))
        for phone in re.findall(r"\b\d{10}\b", text):
            entities.append(EvidenceEntity(label="phone", value=phone))
        seen = set()
        deduped: list[EvidenceEntity] = []
        for entity in entities:
            key = (entity.label, entity.value)
            if key not in seen:
                seen.add(key)
                deduped.append(entity)
        return deduped

    def _extract_timeline(self, text: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return [sentence[:240] for sentence in sentences if re.search(r"\d", sentence)][:8]
