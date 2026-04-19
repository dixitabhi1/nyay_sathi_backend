from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.chat import SourceDocument


class SimilarCaseReference(BaseModel):
    case_title: str
    court: str
    verdict: str
    source_link: str
    similarity_score: str | None = None
    parties: str | None = None
    fir_summary: str | None = None
    charges: str | None = None
    comparison_reasoning: str | None = None
    relevance: str | None = None
    relevance_reason: str | None = None


class CaseAnalysisRequest(BaseModel):
    incident_description: str
    location: str | None = None
    incident_date: str | None = None
    people_involved: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    language: str = "en"
    user_id: str | None = None


class CaseAnalysisResponse(BaseModel):
    case_type: str
    parties: list[str] = Field(default_factory=list)
    legal_sections: list[str] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list)
    legal_issues: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    missing_elements: list[str] = Field(default_factory=list)
    possible_outcomes: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    similar_cases: list[SimilarCaseReference] = Field(default_factory=list)
    final_analysis: str
    case_summary: str | None = None
    applicable_laws: list[str] = Field(default_factory=list)
    legal_reasoning: str | None = None
    possible_punishment: str | None = None
    evidence_required: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    sources: list[SourceDocument] = Field(default_factory=list)


class DraftGenerationRequest(BaseModel):
    draft_type: str
    facts: str
    parties: list[str] = Field(default_factory=list)
    relief_sought: str | None = None
    jurisdiction: str | None = None
    user_id: str | None = None


class DraftGenerationResponse(BaseModel):
    draft_type: str
    content: str
    notes: list[str]


class FirDraftRequest(BaseModel):
    police_station: str
    complainant_name: str
    complainant_address: str
    incident_description: str
    incident_date: str
    incident_location: str
    applicable_sections: list[str] = Field(default_factory=list)
    user_id: str | None = None


class FirDraftResponse(BaseModel):
    fir_text: str
    sections: list[str]
    filing_checklist: list[str]


class CaseStrengthRequest(BaseModel):
    case_description: str | None = None
    evidence_items: int | None = Field(default=None, ge=0)
    witness_count: int | None = Field(default=None, ge=0)
    documentary_support: bool = False
    police_complaint_filed: bool = False
    incident_recency_days: int = Field(default=30, ge=0)
    jurisdiction_match: bool = True
    user_id: str | None = None


class CaseStrengthResponse(BaseModel):
    case_strength_score: int
    strength_label: str
    key_strengths: list[str] = Field(default_factory=list)
    key_weaknesses: list[str] = Field(default_factory=list)
    missing_elements: list[str] = Field(default_factory=list)
    suggested_sections: list[str] = Field(default_factory=list)
    similar_cases: list[SimilarCaseReference] = Field(default_factory=list)
    final_analysis: str
    score: int | None = None
    verdict: str | None = None
    rationale: list[str] = Field(default_factory=list)
