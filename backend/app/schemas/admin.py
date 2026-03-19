from datetime import datetime

from pydantic import BaseModel

from app.schemas.auth import PendingRoleApplicationResponse


class DatasetRefreshRequest(BaseModel):
    requested_by: str
    corpus_path: str | None = None


class DatasetRefreshResponse(BaseModel):
    accepted: bool
    message: str


class CorpusStatusResponse(BaseModel):
    total_documents: int
    total_chunks: int
    statute_chunks: int
    judgment_chunks: int
    mapping_rows: int
    languages: dict[str, int]
    target_statute_chunks: int = 10_000
    target_judgment_passages: int = 50_000


class AdminMetricResponse(BaseModel):
    title: str
    value: str
    detail: str


class AdminLawyerProfileReviewResponse(BaseModel):
    handle: str
    name: str
    verification_status: str
    specialization: str
    city: str
    bar_council_id: str
    linked_user_email: str | None = None
    created_at: datetime


class AdminFIRQueueItemResponse(BaseModel):
    fir_id: str
    workflow: str
    draft_role: str
    status: str
    complainant_name: str | None = None
    police_station: str | None = None
    incident_date: str | None = None
    incident_location: str | None = None
    last_edited_at: datetime


class AdminDashboardResponse(BaseModel):
    metrics: list[AdminMetricResponse]
    pending_applications: list[PendingRoleApplicationResponse]
    recent_lawyer_profiles: list[AdminLawyerProfileReviewResponse]
    recent_firs: list[AdminFIRQueueItemResponse]
    generated_at: datetime
