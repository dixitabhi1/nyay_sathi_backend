from fastapi import APIRouter, Depends

from app.core.security import get_current_admin_user
from app.core.dependencies import get_audit_service, get_corpus_registry
from app.core.dependencies import get_admin_service
from app.models.auth import User
from app.schemas.admin import AdminDashboardResponse, CorpusStatusResponse, DatasetRefreshRequest, DatasetRefreshResponse
from app.services.audit import AuditService
from app.services.admin import AdminService
from app.services.corpus_registry import CorpusRegistry


router = APIRouter()


@router.post("/dataset/refresh", response_model=DatasetRefreshResponse)
def refresh_dataset_index(
    payload: DatasetRefreshRequest,
    audit_service: AuditService = Depends(get_audit_service),
) -> DatasetRefreshResponse:
    response = DatasetRefreshResponse(
        accepted=True,
        message="Dataset refresh job accepted. Run ingestion/scripts/fetch_official_sources.py, ingestion/scripts/build_legal_corpus.py, and rag/indexing/build_faiss_index.py.",
    )
    audit_service.log("admin.dataset_refresh", payload.model_dump(), response.model_dump(), payload.requested_by)
    return response


@router.get("/corpus/status", response_model=CorpusStatusResponse)
def corpus_status(
    registry: CorpusRegistry = Depends(get_corpus_registry),
) -> CorpusStatusResponse:
    return registry.get_status()


@router.get("/dashboard", response_model=AdminDashboardResponse)
def admin_dashboard(
    limit: int = 12,
    admin_service: AdminService = Depends(get_admin_service),
    current_user: User = Depends(get_current_admin_user),
) -> AdminDashboardResponse:
    return admin_service.get_dashboard(limit=limit)
