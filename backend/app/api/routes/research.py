from fastapi import APIRouter, Depends

from app.core.dependencies import get_audit_service, get_legal_engine
from app.schemas.research import ResearchRequest, ResearchResponse
from app.services.audit import AuditService
from app.services.legal_engine import LegalEngine


router = APIRouter()


@router.post("/search", response_model=ResearchResponse)
def research_search(
    payload: ResearchRequest,
    engine: LegalEngine = Depends(get_legal_engine),
    audit_service: AuditService = Depends(get_audit_service),
) -> ResearchResponse:
    response = engine.research(payload)
    audit_service.log("research.search", payload.model_dump(), response.model_dump(), payload.user_id)
    return response

