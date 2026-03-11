from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.dependencies import get_audit_service, get_fir_service
from app.schemas.fir import (
    FIRCompletenessResponse,
    FIRCrimePatternResponse,
    FIRDraftUpdateRequest,
    FIREvidenceAnalysisResponse,
    FIRIntelligenceResponse,
    FIRJurisdictionRequest,
    FIRJurisdictionSuggestion,
    FIRManualRequest,
    FIRRecordResponse,
    FIRSectionPredictionRequest,
    FIRSectionSuggestion,
    FIRStructuredData,
    FIRUploadIntakeResponse,
    FIRVersionsResponse,
    FIRVoiceProcessingResponse,
    FIRVoiceTranscriptRequest,
)
from app.services.audit import AuditService
from app.services.fir_service import FIRService


router = APIRouter()


@router.post("/manual", response_model=FIRRecordResponse)
def create_manual_fir(
    payload: FIRManualRequest,
    fir_service: FIRService = Depends(get_fir_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> FIRRecordResponse:
    response = fir_service.create_manual_fir(payload)
    audit_service.log("fir.manual", payload.model_dump(), response.model_dump(), payload.user_id)
    return response


@router.post("/manual/preview", response_model=FIRUploadIntakeResponse)
def preview_manual_fir(
    payload: FIRManualRequest,
    fir_service: FIRService = Depends(get_fir_service),
) -> FIRUploadIntakeResponse:
    return fir_service.preview_manual_fir(payload)


@router.post("/upload/preview", response_model=FIRUploadIntakeResponse)
async def preview_uploaded_complaint(
    complaint_file: UploadFile = File(...),
    police_station: str | None = Form(default=None),
    fir_service: FIRService = Depends(get_fir_service),
) -> FIRUploadIntakeResponse:
    return await fir_service.preview_uploaded_complaint(complaint_file, police_station)


@router.post("/upload", response_model=FIRRecordResponse)
async def create_fir_from_upload(
    complaint_file: UploadFile = File(...),
    police_station: str | None = Form(default=None),
    user_id: str | None = Form(default=None),
    fir_service: FIRService = Depends(get_fir_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> FIRRecordResponse:
    response = await fir_service.create_fir_from_upload(complaint_file, police_station, user_id)
    audit_service.log(
        "fir.upload",
        {"filename": complaint_file.filename, "police_station": police_station},
        response.model_dump(),
        user_id,
    )
    return response


@router.post("/voice", response_model=FIRRecordResponse)
async def create_fir_from_voice(
    audio_file: UploadFile | None = File(default=None),
    transcript_text: str | None = Form(default=None),
    police_station: str | None = Form(default=None),
    complainant_name: str | None = Form(default=None),
    user_id: str | None = Form(default=None),
    fir_service: FIRService = Depends(get_fir_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> FIRRecordResponse:
    payload = None
    if transcript_text:
        payload = FIRVoiceTranscriptRequest(
            transcript_text=transcript_text,
            police_station=police_station,
            complainant_name=complainant_name,
            user_id=user_id,
        )
    response = await fir_service.create_fir_from_voice(audio_file=audio_file, payload=payload)
    audit_service.log(
        "fir.voice",
        {"filename": getattr(audio_file, "filename", None), "transcript_text": transcript_text},
        response.model_dump(),
        user_id,
    )
    return response


@router.post("/voice/preview", response_model=FIRVoiceProcessingResponse)
async def preview_voice_processing(
    audio_file: UploadFile | None = File(default=None),
    transcript_text: str | None = Form(default=None),
    police_station: str | None = Form(default=None),
    complainant_name: str | None = Form(default=None),
    fir_service: FIRService = Depends(get_fir_service),
) -> FIRVoiceProcessingResponse:
    payload = None
    if transcript_text:
        payload = FIRVoiceTranscriptRequest(
            transcript_text=transcript_text,
            police_station=police_station,
            complainant_name=complainant_name,
        )
    return await fir_service.preview_voice_processing(audio_file=audio_file, payload=payload)


@router.post("/sections/predict", response_model=list[FIRSectionSuggestion])
def predict_sections(
    payload: FIRSectionPredictionRequest,
    fir_service: FIRService = Depends(get_fir_service),
) -> list[FIRSectionSuggestion]:
    return fir_service.predict_sections(payload)


@router.post("/jurisdiction", response_model=FIRJurisdictionSuggestion | None)
def suggest_jurisdiction(
    payload: FIRJurisdictionRequest,
    fir_service: FIRService = Depends(get_fir_service),
) -> FIRJurisdictionSuggestion | None:
    return fir_service.suggest_jurisdiction(payload)


@router.post("/completeness", response_model=FIRCompletenessResponse)
def fir_completeness(
    payload: FIRStructuredData,
    fir_service: FIRService = Depends(get_fir_service),
) -> FIRCompletenessResponse:
    return fir_service.evaluate_completeness(payload)


@router.post("/evidence/analyze", response_model=FIREvidenceAnalysisResponse)
async def analyze_evidence(
    evidence_files: list[UploadFile] = File(...),
    fir_id: str | None = Form(default=None),
    fir_service: FIRService = Depends(get_fir_service),
) -> FIREvidenceAnalysisResponse:
    return await fir_service.analyze_evidence(fir_id=fir_id, files=evidence_files)


@router.get("/analytics/patterns", response_model=FIRCrimePatternResponse)
def crime_patterns(
    window_days: int = 7,
    fir_service: FIRService = Depends(get_fir_service),
) -> FIRCrimePatternResponse:
    return fir_service.crime_patterns(window_days=window_days)


@router.get("/{fir_id}", response_model=FIRRecordResponse)
def get_fir_record(
    fir_id: str,
    fir_service: FIRService = Depends(get_fir_service),
) -> FIRRecordResponse:
    return fir_service.get_fir_record(fir_id)


@router.put("/{fir_id}/draft", response_model=FIRRecordResponse)
def update_fir_draft(
    fir_id: str,
    payload: FIRDraftUpdateRequest,
    fir_service: FIRService = Depends(get_fir_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> FIRRecordResponse:
    response = fir_service.update_draft(fir_id, payload)
    audit_service.log("fir.update_draft", payload.model_dump(), response.model_dump(), payload.edited_by)
    return response


@router.get("/{fir_id}/versions", response_model=FIRVersionsResponse)
def list_fir_versions(
    fir_id: str,
    fir_service: FIRService = Depends(get_fir_service),
) -> FIRVersionsResponse:
    return fir_service.list_versions(fir_id)


@router.get("/{fir_id}/intelligence", response_model=FIRIntelligenceResponse)
def fir_intelligence(
    fir_id: str,
    fir_service: FIRService = Depends(get_fir_service),
) -> FIRIntelligenceResponse:
    return fir_service.intelligence_summary(fir_id)


@router.post("/{fir_id}/evidence", response_model=FIRRecordResponse)
async def upload_fir_evidence(
    fir_id: str,
    evidence_files: list[UploadFile] = File(...),
    fir_service: FIRService = Depends(get_fir_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> FIRRecordResponse:
    response = await fir_service.attach_evidence(fir_id, evidence_files)
    audit_service.log(
        "fir.evidence",
        {"fir_id": fir_id, "files": [upload.filename for upload in evidence_files]},
        response.model_dump(),
    )
    return response
