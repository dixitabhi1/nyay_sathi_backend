from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.auth import User
from app.schemas.history import UserHistoryResponse
from app.services.history import UserHistoryService
from app.core.dependencies import get_history_service


router = APIRouter()


@router.get("", response_model=UserHistoryResponse)
def list_history(
    category: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    history_service: UserHistoryService = Depends(get_history_service),
) -> UserHistoryResponse:
    return history_service.list_history(current_user.id, category=category, limit=limit)
