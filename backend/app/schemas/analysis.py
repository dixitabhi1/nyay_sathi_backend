from pydantic import BaseModel, Field

from app.schemas.chat import SourceDocument


class CaseAnalysisRequest(BaseModel):
    incident_description: str
    location: str | None = None
    incident_date: str | None = None
    people_involved: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    language: str = "en"
    user_id: str | None = None


class CaseAnalysisResponse(BaseModel):
    case_summary: str
    applicable_laws: list[str]
    legal_reasoning: str
    possible_punishment: str
    evidence_required: list[str]
    recommended_next_steps: list[str]
    sources: list[SourceDocument]


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
    evidence_items: int = Field(ge=0)
    witness_count: int = Field(ge=0)
    documentary_support: bool = False
    police_complaint_filed: bool = False
    incident_recency_days: int = Field(default=30, ge=0)
    jurisdiction_match: bool = True
    user_id: str | None = None


class CaseStrengthResponse(BaseModel):
    score: int
    verdict: str
    rationale: list[str]

