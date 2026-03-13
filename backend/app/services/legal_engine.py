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

        contextual_question = self._build_contextual_question(payload)
        scope = self.retriever.assess_scope(contextual_question)
        if not scope["in_scope"]:
            return self._out_of_scope_response(scope)
        prioritized_hits = self._filter_grounded_hits(self._prioritize_hits_for_question(contextual_question, scope["hits"]))
        if not prioritized_hits:
            return self._insufficient_grounding_response()
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
        formatted: list[str] = []
        for index, source in enumerate(sources, start=1):
            formatted.append(
                "\n".join(
                    [
                        f"[Source {index}] {source.title}",
                        f"Citation: {source.citation}",
                        f"Type: {source.source_type}",
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
        if "evidence act" in haystack or "65b" in haystack:
            return "https://www.indiacode.nic.in/handle/123456789/2187"
        if "contract act" in haystack:
            return "https://www.indiacode.nic.in/handle/123456789/2185"
        if "ipc" in haystack or "penal code" in haystack:
            return "https://www.indiacode.nic.in/bitstream/123456789/2263/1/A1860-45.pdf"
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

        if "bnss" in normalized or "bharatiya nagarik suraksha sanhita" in normalized:
            source = SourceDocument(
                title="Bharatiya Nagarik Suraksha Sanhita, 2023",
                citation="India Code Act No. 46 of 2023",
                excerpt=(
                    "In the official India Code text of the Bharatiya Nagarik Suraksha Sanhita, 2023, "
                    "the statute runs from section 1 to section 531."
                ),
                source_type="statute",
                score=1.0,
                source_url="https://www.indiacode.nic.in/handle/123456789/21544",
            )
            return ChatResponse(
                answer=(
                    "The Bharatiya Nagarik Suraksha Sanhita, 2023 contains 531 sections. "
                    "This is based on the official India Code text, where the statute runs from section 1 to section 531."
                ),
                reasoning=(
                    "This answer is taken from the statute structure itself rather than semantic retrieval. "
                    "For structural questions, NyayaSetu should use the official act text directly."
                ),
                sources=[source],
                in_scope=True,
            )

        if re.search(r"\bbns\b", normalized) or "bharatiya nyaya sanhita" in normalized:
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

        if re.search(r"\bbsa\b", normalized) or "bharatiya sakshya adhiniyam" in normalized:
            source = SourceDocument(
                title="Bharatiya Sakshya Adhiniyam, 2023",
                citation="India Code Act No. 47 of 2023",
                excerpt=(
                    "In the official India Code text of the Bharatiya Sakshya Adhiniyam, 2023, "
                    "the statute runs from section 1 to section 170."
                ),
                source_type="statute",
                score=1.0,
                source_url="https://www.indiacode.nic.in/handle/123456789/20063",
            )
            return ChatResponse(
                answer=(
                    "The Bharatiya Sakshya Adhiniyam, 2023 contains 170 sections. "
                    "This is based on the official India Code text, where the statute runs from section 1 to section 170."
                ),
                reasoning=(
                    "This answer is taken from the statute structure itself rather than semantic retrieval. "
                    "For structural questions, NyayaSetu should use the official act text directly."
                ),
                sources=[source],
                in_scope=True,
            )

        return None

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
        explanation = self._plain_language_summary(lead)
        support_lines = [
            f"- {source.citation}: {self._plain_language_summary(source)}"
            for source in supporting
        ]
        next_steps = self._suggest_question_specific_steps(question, sources)
        answer_parts = [
            f"Short answer: {explanation}",
            f"Most relevant authority: {lead.citation}.",
        ]
        if recent_context:
            answer_parts.append(f"Conversation context used: {recent_context}")
        if support_lines:
            answer_parts.append("Supporting material:\n" + "\n".join(support_lines))
        if next_steps:
            answer_parts.append("Practical next steps:\n" + "\n".join(f"- {step}" for step in next_steps))
        answer_parts.append(f"Grounded citations: {citations}.")
        reasoning = (
            "NyayaSetu is in retrieval-first mode, so this answer was composed from the top grounded legal sources. "
            f"It prioritized {citations} and converted the retrieved excerpts into plain-language guidance."
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

    def _plain_language_summary(self, source: SourceDocument) -> str:
        excerpt = re.sub(r"\s+", " ", source.excerpt).strip()
        sentence = re.split(r"(?<=[.!?])\s+", excerpt)[0].strip()
        if sentence:
            return sentence
        return excerpt[:220]

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
