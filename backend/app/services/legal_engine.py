from __future__ import annotations

import json
import re
from textwrap import dedent

from fastapi import HTTPException, UploadFile

from app.core.config import Settings
from app.schemas.analysis import (
    CaseAnalysisRequest,
    CaseAnalysisResponse,
    CaseStrengthRequest,
    CaseStrengthResponse,
    DraftGenerationRequest,
    DraftGenerationResponse,
    FirDraftRequest,
    FirDraftResponse,
)
from app.schemas.chat import ChatRequest, ChatResponse, SourceDocument
from app.schemas.documents import (
    ContractAnalysisResponse,
    ContractClause,
    ContractRisk,
    EvidenceAnalysisResponse,
    EvidenceEntity,
)
from app.schemas.research import ResearchRequest, ResearchResponse
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

        scope = self.retriever.assess_scope(payload.question)
        if not scope["in_scope"]:
            return ChatResponse(
                answer="This question appears to be outside NyayaSetu's legal assistance scope.",
                reasoning=(
                    "NyayaSetu compares the query embedding against the legal corpus and legal-domain anchor embeddings. "
                    "This prompt did not land close enough to legal materials to justify a grounded answer."
                ),
                sources=[],
                in_scope=False,
                scope_warning=(
                    "Ask a legal question about Indian statutes, BNS or IPC sections, FIRs, contracts, rights, judgments, or legal procedure. "
                    f"Embedding scope scores: legal={scope['legal_anchor_score']}, non-legal={scope['non_legal_anchor_score']}, corpus={scope['top_corpus_score']}."
                ),
            )
        prioritized_hits = self._prioritize_hits_for_question(payload.question, scope["hits"])
        sources = [
            SourceDocument(
                title=item["title"],
                citation=item["citation"],
                excerpt=item["text"][:280],
                source_type=item.get("source_type", "statute"),
                score=round(item["score"], 4),
                source_url=item.get("source_url") or self._default_source_url(item["citation"], item["title"]),
            )
            for item in prioritized_hits
        ]
        context = self._format_sources_for_prompt(sources)
        if self.settings.inference_provider.lower() == "mock":
            parsed = self._synthesize_chat_answer(payload.question, sources)
        else:
            prompt = dedent(
                f"""
                User question: {payload.question}
                Preferred language: {payload.language}

                Retrieved legal context:
                {context}

                Answer with a plain-language explanation and concise legal reasoning.
                """
            ).strip()
            generated = self.inference.generate(
                "You are NyayaSetu, a self-hosted legal assistant focused on Indian law.",
                prompt,
            )
            parsed = self._parse_generation(generated)
        return ChatResponse(
            answer=parsed.get("answer") or self._fallback_answer(sources),
            reasoning=parsed.get("reasoning") or "The answer is grounded in the retrieved legal materials listed below.",
            sources=sources,
            in_scope=True,
        )

    def analyze_case(self, payload: CaseAnalysisRequest) -> CaseAnalysisResponse:
        query = " ".join([payload.incident_description, payload.location or "", " ".join(payload.evidence)])
        sources = self._retrieve_sources(query)
        laws = [source.citation for source in sources]
        punishment = "; ".join(sorted({source.excerpt.split(".")[0] for source in sources})) or "Punishment depends on the final charge sheet and judicial findings."
        next_steps = [
            "Preserve original records, screenshots, and device metadata.",
            "Prepare a chronology of events with dates, times, and witnesses.",
            "Consult a lawyer before filing or responding to legal notices.",
        ]
        if not payload.evidence:
            next_steps.insert(0, "Collect primary evidence before approaching the police or court.")

        reasoning_prompt = dedent(
            f"""
            Incident: {payload.incident_description}
            Location: {payload.location}
            Date: {payload.incident_date}
            People involved: {", ".join(payload.people_involved)}
            Evidence: {", ".join(payload.evidence)}
            Context:
            {self._format_sources_for_prompt(sources)}
            """
        ).strip()
        generated = self.inference.generate(
            "Generate a structured legal analysis for a citizen-facing assistant. Explain why the cited sections may apply.",
            reasoning_prompt,
        )
        parsed = self._parse_generation(generated)
        return CaseAnalysisResponse(
            case_summary=f"Incident at {payload.location or 'an unspecified location'} involving {len(payload.people_involved) or 1} primary parties.",
            applicable_laws=laws,
            legal_reasoning=parsed.get("reasoning") or self._fallback_reasoning(sources),
            possible_punishment=punishment,
            evidence_required=self._suggest_evidence(payload.evidence),
            recommended_next_steps=next_steps,
            sources=sources,
        )

    def score_case_strength(self, payload: CaseStrengthRequest) -> CaseStrengthResponse:
        score = 25
        rationale: list[str] = []
        score += min(payload.evidence_items * 8, 24)
        if payload.evidence_items:
            rationale.append("Physical or digital evidence improves provability.")
        score += min(payload.witness_count * 6, 18)
        if payload.witness_count:
            rationale.append("Independent witnesses improve credibility.")
        if payload.documentary_support:
            score += 15
            rationale.append("Documentary support reduces factual ambiguity.")
        if payload.police_complaint_filed:
            score += 10
            rationale.append("A contemporaneous complaint helps establish chronology.")
        if payload.incident_recency_days <= 30:
            score += 10
            rationale.append("Recent incidents are easier to corroborate.")
        if not payload.jurisdiction_match:
            score -= 15
            rationale.append("Jurisdiction mismatch can slow or weaken proceedings.")
        score = max(0, min(score, 100))
        verdict = "strong" if score >= 75 else "moderate" if score >= 45 else "weak"
        if not rationale:
            rationale.append("The baseline score is low because the case lacks corroborating inputs.")
        return CaseStrengthResponse(score=score, verdict=verdict, rationale=rationale)

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
        hits = self._retrieve_sources(payload.query, payload.top_k)
        summary = "Relevant statutes and precedents retrieved for the research query."
        return ResearchResponse(summary=summary, hits=hits)

    async def analyze_contract(
        self,
        contract_file: UploadFile | None,
        contract_text: str | None,
        user_id: str | None = None,
    ) -> ContractAnalysisResponse:
        _ = user_id
        text = await self._resolve_text(contract_file, contract_text, "contract text or upload")
        clauses = self._extract_clauses(text)
        risks = self._detect_contract_risks(text)
        missing = self._missing_contract_clauses(text)
        return ContractAnalysisResponse(
            summary=f"Contract reviewed with {len(clauses)} detected clauses and {len(risks)} flagged risks.",
            clauses=clauses,
            risks=risks,
            missing_clauses=missing,
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
        return [
            SourceDocument(
                title=item["title"],
                citation=item["citation"],
                excerpt=item["text"][:280],
                source_type=item.get("source_type", "statute"),
                score=round(item["score"], 4),
                source_url=item.get("source_url") or self._default_source_url(item["citation"], item["title"]),
            )
            for item in results
        ]

    def _format_sources_for_prompt(self, sources: list[SourceDocument]) -> str:
        return "\n\n".join(
            f"{source.title} ({source.citation})\n{source.excerpt}"
            for source in sources
        )

    def _default_source_url(self, citation: str, title: str) -> str | None:
        haystack = f"{citation} {title}".lower()
        if "bns" in haystack or "bharatiya nyaya sanhita" in haystack:
            return "https://www.indiacode.nic.in/handle/123456789/20062"
        if "evidence act" in haystack or "65b" in haystack:
            return "https://www.indiacode.nic.in/handle/123456789/2187"
        if "contract act" in haystack:
            return "https://www.indiacode.nic.in/handle/123456789/2185"
        if "ipc" in haystack or "penal code" in haystack:
            return "https://www.indiacode.nic.in/bitstream/123456789/2263/1/A1860-45.pdf"
        return None

    def _parse_generation(self, generated: str) -> dict:
        try:
            return json.loads(generated)
        except json.JSONDecodeError:
            return {"answer": generated.strip(), "reasoning": generated.strip()}

    def _resolve_structural_statute_question(self, question: str) -> ChatResponse | None:
        normalized = question.lower().strip()
        if not re.search(r"\bhow many\b.*\bsections?\b|\bnumber of sections?\b", normalized):
            return None

        if "bns" in normalized or "bharatiya nyaya sanhita" in normalized:
            source = SourceDocument(
                title="Bharatiya Nyaya Sanhita, 2023",
                citation="India Code Act No. 45 of 2023",
                excerpt=(
                    "In the India Code text of the Bharatiya Nyaya Sanhita, 2023, the Arrangement of Sections runs "
                    "from section 1 to section 358."
                ),
                source_type="statute",
                score=1.0,
                source_url="https://www.indiacode.nic.in/handle/123456789/20062",
            )
            return ChatResponse(
                answer=(
                    "The Bharatiya Nyaya Sanhita, 2023 contains 358 sections. This is based on the official India Code text, "
                    "where the arrangement of sections runs from section 1 to section 358."
                ),
                reasoning=(
                    "This answer is taken from the statute structure itself rather than from a penal-section mapping. "
                    "For structural questions like this, NyayaSetu should use the official act text instead of retrieving unrelated offence provisions."
                ),
                sources=[source],
                in_scope=True,
            )

        return None

    def _prioritize_hits_for_question(self, question: str, hits: list[dict]) -> list[dict]:
        normalized = question.lower()
        prioritized = hits
        if "bns" in normalized or "bharatiya nyaya sanhita" in normalized:
            filtered = [
                item for item in hits
                if "bns" in f"{item.get('title', '')} {item.get('citation', '')} {item.get('text', '')}".lower()
            ]
            if filtered:
                prioritized = filtered
        return prioritized

    def _synthesize_chat_answer(self, question: str, sources: list[SourceDocument]) -> dict:
        if not sources:
            return {
                "answer": "I could not retrieve a matching legal passage for that question from the current corpus.",
                "reasoning": "NyayaSetu is running without a generation model, so the reply must stay tied to retrieved legal material already indexed.",
            }

        lead = sources[0]
        answer = (
            f"Based on the retrieved legal material, the closest match is {lead.citation}. "
            f"{lead.excerpt}"
        )
        if re.search(r"\bexplain\b|\bwhat is\b|\bmeaning\b", question.lower()):
            answer = lead.excerpt
        reasoning = (
            "NyayaSetu is currently in retrieval-first mode, so this response is composed directly from the most relevant indexed legal source "
            "instead of a separate generation model."
        )
        return {"answer": answer, "reasoning": reasoning}

    def _fallback_answer(self, sources: list[SourceDocument]) -> str:
        if not sources:
            return "No matching legal materials were retrieved. Rephrase the question or expand the legal corpus."
        lead = sources[0]
        return f"The strongest retrieved authority is {lead.citation}. Review the cited material and consult counsel before acting."

    def _fallback_reasoning(self, sources: list[SourceDocument]) -> str:
        return "The incident pattern overlaps with the retrieved provisions, subject to factual verification and procedural requirements."

    def _suggest_evidence(self, current_evidence: list[str]) -> list[str]:
        baseline = ["Original screenshots or communications", "Witness statements", "Identity and address proof"]
        if not current_evidence:
            return baseline
        return current_evidence + [item for item in baseline if item not in current_evidence]

    def _extract_clauses(self, text: str) -> list[ContractClause]:
        matches = re.split(r"\n(?=[A-Z][A-Za-z ]{3,40}:)", text)
        clauses: list[ContractClause] = []
        for chunk in matches[:12]:
            lines = [line.strip() for line in chunk.splitlines() if line.strip()]
            if not lines:
                continue
            heading = lines[0].rstrip(":")
            body = " ".join(lines[1:]) or lines[0]
            clauses.append(ContractClause(heading=heading, content=body[:500]))
        if not clauses:
            clauses.append(ContractClause(heading="General Terms", content=text[:700]))
        return clauses

    def _detect_contract_risks(self, text: str) -> list[ContractRisk]:
        lowered = text.lower()
        risks: list[ContractRisk] = []
        if "automatic renewal" in lowered:
            risks.append(
                ContractRisk(
                    severity="medium",
                    issue="Automatic renewal clause detected.",
                    recommendation="Add explicit notice and termination windows before renewal.",
                )
            )
        if "sole discretion" in lowered or "without notice" in lowered:
            risks.append(
                ContractRisk(
                    severity="high",
                    issue="Unilateral control language may create imbalance.",
                    recommendation="Limit discretionary powers and require prior written notice.",
                )
            )
        if "indemnify" in lowered and "cap" not in lowered:
            risks.append(
                ContractRisk(
                    severity="high",
                    issue="Indemnity appears uncapped.",
                    recommendation="Negotiate liability caps and carve-outs.",
                )
            )
        if not risks:
            risks.append(
                ContractRisk(
                    severity="low",
                    issue="No obvious high-risk pattern matched the baseline rules.",
                    recommendation="Run clause-level legal review before execution.",
                )
            )
        return risks

    def _missing_contract_clauses(self, text: str) -> list[str]:
        lowered = text.lower()
        expected = {
            "termination": "Termination",
            "governing law": "Governing Law",
            "dispute resolution": "Dispute Resolution",
            "confidentiality": "Confidentiality",
            "limitation of liability": "Limitation of Liability",
        }
        return [label for key, label in expected.items() if key not in lowered]

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
