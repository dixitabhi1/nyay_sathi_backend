from fastapi import APIRouter, Depends

from app.core.dependencies import get_audit_service, get_legal_engine
from app.core.security import get_optional_current_user
from app.models.auth import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.audit import AuditService
from app.services.legal_engine import LegalEngine


router = APIRouter()


@router.post("/query", response_model=ChatResponse)
def query_chatbot(
    payload: ChatRequest,
    engine: LegalEngine = Depends(get_legal_engine),
    audit_service: AuditService = Depends(get_audit_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> ChatResponse:
    payload.user_id = current_user.id if current_user else payload.user_id
    response = engine.answer_question(payload)
    audit_service.log("chat.query", payload.model_dump(), response.model_dump(), payload.user_id)
    return response
