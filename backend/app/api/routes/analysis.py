from fastapi import APIRouter, Depends

from app.core.dependencies import get_audit_service, get_legal_engine
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
from app.services.audit import AuditService
from app.services.legal_engine import LegalEngine


router = APIRouter()


@router.post("/case", response_model=CaseAnalysisResponse)
def analyze_case(
    payload: CaseAnalysisRequest,
    engine: LegalEngine = Depends(get_legal_engine),
    audit_service: AuditService = Depends(get_audit_service),
) -> CaseAnalysisResponse:
    response = engine.analyze_case(payload)
    audit_service.log("analysis.case", payload.model_dump(), response.model_dump(), payload.user_id)
    return response


@router.post("/strength", response_model=CaseStrengthResponse)
def score_case_strength(
    payload: CaseStrengthRequest,
    engine: LegalEngine = Depends(get_legal_engine),
    audit_service: AuditService = Depends(get_audit_service),
) -> CaseStrengthResponse:
    response = engine.score_case_strength(payload)
    audit_service.log("analysis.strength", payload.model_dump(), response.model_dump(), payload.user_id)
    return response


@router.post("/draft", response_model=DraftGenerationResponse)
def generate_draft(
    payload: DraftGenerationRequest,
    engine: LegalEngine = Depends(get_legal_engine),
    audit_service: AuditService = Depends(get_audit_service),
) -> DraftGenerationResponse:
    response = engine.generate_draft(payload)
    audit_service.log("analysis.draft", payload.model_dump(), response.model_dump(), payload.user_id)
    return response


@router.post("/fir", response_model=FirDraftResponse)
def generate_fir(
    payload: FirDraftRequest,
    engine: LegalEngine = Depends(get_legal_engine),
    audit_service: AuditService = Depends(get_audit_service),
) -> FirDraftResponse:
    response = engine.generate_fir(payload)
    audit_service.log("analysis.fir", payload.model_dump(), response.model_dump(), payload.user_id)
    return response

