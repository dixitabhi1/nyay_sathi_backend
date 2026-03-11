from fastapi import APIRouter, Depends

from app.core.dependencies import get_audit_service, get_corpus_registry
from app.schemas.admin import CorpusStatusResponse, DatasetRefreshRequest, DatasetRefreshResponse
from app.services.audit import AuditService
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
