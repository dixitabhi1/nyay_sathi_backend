from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_audit_service, get_fir_service
from app.core.security import get_optional_current_user
from app.models.auth import User
from app.schemas.fir import (
    FIRCompletenessResponse,
    FIRCrimePatternResponse,
    FIRDraftUpdateRequest,
    FIREvidenceAnalysisResponse,
    FIRIntelligenceResponse,
    FIRJurisdictionRequest,
    FIRJurisdictionSuggestion,
    FIRManualRequest,
    FIRRecordListResponse,
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
    current_user: User | None = Depends(get_optional_current_user),
) -> FIRRecordResponse:
    payload.user_id = current_user.id if current_user else payload.user_id
    try:
        response = fir_service.create_manual_fir(payload, viewer=current_user)
        audit_service.log("fir.manual", payload.model_dump(), response.model_dump(), payload.user_id)
        return response
    except HTTPException:
        raise
    except Exception:
        return fir_service.create_manual_fir_failsafe(payload, viewer=current_user)


@router.post("/manual/preview", response_model=FIRUploadIntakeResponse)
def preview_manual_fir(
    payload: FIRManualRequest,
    fir_service: FIRService = Depends(get_fir_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> FIRUploadIntakeResponse:
    payload.user_id = current_user.id if current_user else payload.user_id
    return fir_service.preview_manual_fir(payload, viewer=current_user)


@router.post("/upload/preview", response_model=FIRUploadIntakeResponse)
async def preview_uploaded_complaint(
    complaint_file: UploadFile = File(...),
    police_station: str | None = Form(default=None),
    draft_role: str = Form(default="citizen_application"),
    language: str = Form(default="en"),
    fir_service: FIRService = Depends(get_fir_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> FIRUploadIntakeResponse:
    return await fir_service.preview_uploaded_complaint(
        complaint_file,
        police_station,
        draft_role=draft_role,
        draft_language=language,
        viewer=current_user,
    )


@router.post("/upload", response_model=FIRRecordResponse)
async def create_fir_from_upload(
    complaint_file: UploadFile = File(...),
    police_station: str | None = Form(default=None),
    draft_role: str = Form(default="citizen_application"),
    language: str = Form(default="en"),
    user_id: str | None = Form(default=None),
    fir_service: FIRService = Depends(get_fir_service),
    audit_service: AuditService = Depends(get_audit_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> FIRRecordResponse:
    user_id = current_user.id if current_user else user_id
    try:
        response = await fir_service.create_fir_from_upload(
            complaint_file,
            police_station,
            draft_role=draft_role,
            draft_language=language,
            user_id=user_id,
            viewer=current_user,
        )
        audit_service.log(
            "fir.upload",
            {"filename": complaint_file.filename, "police_station": police_station},
            response.model_dump(),
            user_id,
        )
        return response
    except HTTPException:
        raise
    except Exception:
        return await fir_service.create_fir_from_upload_failsafe(
            complaint_file,
            police_station,
            draft_role=draft_role,
            draft_language=language,
            viewer=current_user,
        )


@router.post("/voice", response_model=FIRRecordResponse)
async def create_fir_from_voice(
    audio_file: UploadFile | None = File(default=None),
    transcript_text: str | None = Form(default=None),
    police_station: str | None = Form(default=None),
    complainant_name: str | None = Form(default=None),
    draft_role: str = Form(default="citizen_application"),
    language: str = Form(default="en"),
    user_id: str | None = Form(default=None),
    fir_service: FIRService = Depends(get_fir_service),
    audit_service: AuditService = Depends(get_audit_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> FIRRecordResponse:
    user_id = current_user.id if current_user else user_id
    payload = None
    if any(
        [
            transcript_text is not None,
            police_station is not None,
            complainant_name is not None,
            draft_role != "citizen_application",
            language != "en",
            user_id is not None,
        ]
    ):
        payload = FIRVoiceTranscriptRequest(
            transcript_text=transcript_text or "",
            police_station=police_station,
            complainant_name=complainant_name,
            draft_role=draft_role,
            language=language,
            user_id=user_id,
        )
    try:
        response = await fir_service.create_fir_from_voice(audio_file=audio_file, payload=payload, viewer=current_user)
        audit_service.log(
            "fir.voice",
            {"filename": getattr(audio_file, "filename", None), "transcript_text": transcript_text},
            response.model_dump(),
            user_id,
        )
        return response
    except HTTPException:
        raise
    except Exception:
        return await fir_service.create_fir_from_voice_failsafe(
            audio_file=audio_file,
            payload=payload,
            viewer=current_user,
        )


@router.post("/voice/preview", response_model=FIRVoiceProcessingResponse)
async def preview_voice_processing(
    audio_file: UploadFile | None = File(default=None),
    transcript_text: str | None = Form(default=None),
    police_station: str | None = Form(default=None),
    complainant_name: str | None = Form(default=None),
    draft_role: str = Form(default="citizen_application"),
    language: str = Form(default="en"),
    fir_service: FIRService = Depends(get_fir_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> FIRVoiceProcessingResponse:
    payload = None
    if any(
        [
            transcript_text is not None,
            police_station is not None,
            complainant_name is not None,
            draft_role != "citizen_application",
            language != "en",
            current_user is not None,
        ]
    ):
        payload = FIRVoiceTranscriptRequest(
            transcript_text=transcript_text or "",
            police_station=police_station,
            complainant_name=complainant_name,
            draft_role=draft_role,
            language=language,
            user_id=current_user.id if current_user else None,
        )
    return await fir_service.preview_voice_processing(audio_file=audio_file, payload=payload, viewer=current_user)


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


@router.get("", response_model=FIRRecordListResponse)
def list_fir_records(
    limit: int = 25,
    fir_service: FIRService = Depends(get_fir_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> FIRRecordListResponse:
    return fir_service.list_records(limit=limit, user_id=current_user.id if current_user else None)


@router.get("/{fir_id}", response_model=FIRRecordResponse)
def get_fir_record(
    fir_id: str,
    fir_service: FIRService = Depends(get_fir_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> FIRRecordResponse:
    return fir_service.get_fir_record(fir_id, user_id=current_user.id if current_user else None, viewer=current_user)


@router.put("/{fir_id}/draft", response_model=FIRRecordResponse)
def update_fir_draft(
    fir_id: str,
    payload: FIRDraftUpdateRequest,
    fir_service: FIRService = Depends(get_fir_service),
    audit_service: AuditService = Depends(get_audit_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> FIRRecordResponse:
    payload.edited_by = current_user.id if current_user else payload.edited_by
    response = fir_service.update_draft(
        fir_id,
        payload,
        user_id=current_user.id if current_user else None,
        viewer=current_user,
    )
    audit_service.log("fir.update_draft", payload.model_dump(), response.model_dump(), payload.edited_by)
    return response


@router.get("/{fir_id}/versions", response_model=FIRVersionsResponse)
def list_fir_versions(
    fir_id: str,
    fir_service: FIRService = Depends(get_fir_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> FIRVersionsResponse:
    return fir_service.list_versions(
        fir_id,
        user_id=current_user.id if current_user else None,
        viewer=current_user,
    )


@router.get("/{fir_id}/intelligence", response_model=FIRIntelligenceResponse)
def fir_intelligence(
    fir_id: str,
    fir_service: FIRService = Depends(get_fir_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> FIRIntelligenceResponse:
    return fir_service.intelligence_summary(
        fir_id,
        user_id=current_user.id if current_user else None,
        viewer=current_user,
    )


@router.post("/{fir_id}/evidence", response_model=FIRRecordResponse)
async def upload_fir_evidence(
    fir_id: str,
    evidence_files: list[UploadFile] = File(...),
    fir_service: FIRService = Depends(get_fir_service),
    audit_service: AuditService = Depends(get_audit_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> FIRRecordResponse:
    response = await fir_service.attach_evidence(
        fir_id,
        evidence_files,
        user_id=current_user.id if current_user else None,
        viewer=current_user,
    )
    audit_service.log(
        "fir.evidence",
        {"fir_id": fir_id, "files": [upload.filename for upload in evidence_files]},
        response.model_dump(),
    )
    return response


@router.get("/{fir_id}/documents/{document_kind}.pdf")
def download_fir_document_pdf(
    fir_id: str,
    document_kind: str,
    language: str | None = None,
    fir_service: FIRService = Depends(get_fir_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> StreamingResponse:
    filename, pdf_bytes = fir_service.render_document_pdf(
        fir_id,
        document_kind=document_kind,
        user_id=current_user.id if current_user else None,
        language=language,
        viewer=current_user,
    )
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
