from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.chat import SourceDocument


class ResearchRequest(BaseModel):
    query: str | None = None
    user_query: str | None = None
    mode: Literal["case_search", "fir_analysis"] = "case_search"
    user_role: Literal["basic", "premium"] = "basic"
    top_k: int = Field(default=5, ge=1, le=20)
    user_id: str | None = None

    @model_validator(mode="after")
    def ensure_query(self) -> "ResearchRequest":
        if not (self.user_query or self.query):
            raise ValueError("Provide query or user_query.")
        return self

    @property
    def effective_query(self) -> str:
        return (self.user_query or self.query or "").strip()


class ResearchCaseResult(BaseModel):
    case_title: str
    court: str
    similarity_score: str
    parties: str
    fir_summary: str
    charges: str
    verdict: str
    source_link: str
    comparison_reasoning: str


class ResearchFIRAnalysis(BaseModel):
    improved_draft: str = ""
    suggested_sections: str = ""
    risk_analysis: str = ""


class ResearchResponse(BaseModel):
    status: str
    mode: Literal["case_search", "fir_analysis"]
    results: list[ResearchCaseResult] = Field(default_factory=list)
    fir_analysis: ResearchFIRAnalysis = Field(default_factory=ResearchFIRAnalysis)
    message: str | None = None
    summary: str | None = None
    hits: list[SourceDocument] = Field(default_factory=list)
