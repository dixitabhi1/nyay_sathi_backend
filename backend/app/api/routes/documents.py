from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.dependencies import get_audit_service, get_legal_engine
from app.schemas.documents import ContractAnalysisResponse, EvidenceAnalysisResponse
from app.services.audit import AuditService
from app.services.legal_engine import LegalEngine


router = APIRouter()


@router.post("/contract/analyze", response_model=ContractAnalysisResponse)
async def analyze_contract(
    contract_file: UploadFile | None = File(default=None),
    contract_text: str | None = Form(default=None),
    user_id: str | None = Form(default=None),
    engine: LegalEngine = Depends(get_legal_engine),
    audit_service: AuditService = Depends(get_audit_service),
) -> ContractAnalysisResponse:
    response = await engine.analyze_contract(contract_file, contract_text, user_id)
    audit_service.log("documents.contract", {"filename": getattr(contract_file, "filename", None)}, response.model_dump(), user_id)
    return response


@router.post("/evidence/analyze", response_model=EvidenceAnalysisResponse)
async def analyze_evidence(
    evidence_file: UploadFile | None = File(default=None),
    evidence_text: str | None = Form(default=None),
    user_id: str | None = Form(default=None),
    engine: LegalEngine = Depends(get_legal_engine),
    audit_service: AuditService = Depends(get_audit_service),
) -> EvidenceAnalysisResponse:
    response = await engine.analyze_evidence(evidence_file, evidence_text, user_id)
    audit_service.log("documents.evidence", {"filename": getattr(evidence_file, "filename", None)}, response.model_dump(), user_id)
    return response

