import logging

from fastapi import APIRouter, Depends

from app.db.session import init_db
from app.core.security import get_current_user
from app.models.auth import User
from app.schemas.history import UserHistoryResponse
from app.services.history import UserHistoryService


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=UserHistoryResponse)
def list_history(
    category: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
) -> UserHistoryResponse:
    try:
        init_db()
        history_service = UserHistoryService()
        return history_service.list_history(current_user.id, category=category, limit=limit)
    except Exception as exc:  # pragma: no cover - final protection for hosted runtime edge cases
        logger.warning("History route fallback for user %s: %s", current_user.id, exc)
        return UserHistoryResponse(items=[])
