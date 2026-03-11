from pydantic import BaseModel, Field


class ContractClause(BaseModel):
    heading: str
    content: str


class ContractRisk(BaseModel):
    severity: str
    issue: str
    recommendation: str


class ContractAnalysisResponse(BaseModel):
    summary: str
    clauses: list[ContractClause]
    risks: list[ContractRisk]
    missing_clauses: list[str]


class EvidenceEntity(BaseModel):
    label: str
    value: str


class EvidenceAnalysisResponse(BaseModel):
    extracted_text: str
    entities: list[EvidenceEntity]
    timeline: list[str]
    observations: list[str] = Field(default_factory=list)

