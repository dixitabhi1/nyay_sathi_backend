import json

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.core.dependencies import get_audit_service, get_document_marketplace_service, get_legal_engine
from app.core.security import get_current_user, get_optional_current_user
from app.models.auth import User
from app.schemas.documents import (
    ContractAnalysisResponse,
    DocumentOrderDetailResponse,
    DocumentOrderListResponse,
    DocumentPaymentVerificationRequest,
    DocumentTemplateCheckoutRequest,
    DocumentTemplateCheckoutResponse,
    DocumentTemplateDetailResponse,
    DocumentTemplateDirectoryResponse,
    DocumentTemplateField,
    EvidenceAnalysisResponse,
)
from app.services.audit import AuditService
from app.services.document_marketplace import DocumentMarketplaceService
from app.services.legal_engine import LegalEngine


router = APIRouter()


def _parse_fields_json(raw: str | None) -> list[DocumentTemplateField]:
    try:
        payload = json.loads(raw or "[]")
        if not isinstance(payload, list):
            raise ValueError("Expected a list.")
        return [DocumentTemplateField.model_validate(item) for item in payload]
    except Exception as exc:
        raise ValueError("Document fields must be a valid JSON array.") from exc


def _parse_tags_json(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
        if isinstance(payload, list):
            return [str(item) for item in payload]
    except Exception:
        pass
    return [part.strip() for part in raw.split(",") if part.strip()]


def _parse_sample_input_json(raw: str | None) -> dict[str, str]:
    try:
        payload = json.loads(raw or "{}")
        if isinstance(payload, dict):
            return {str(key): str(value) for key, value in payload.items()}
    except Exception as exc:
        raise ValueError("Sample input must be a valid JSON object.") from exc
    return {}


@router.post("/contract/analyze", response_model=ContractAnalysisResponse)
async def analyze_contract(
    contract_file: UploadFile | None = File(default=None),
    contract_text: str | None = Form(default=None),
    user_id: str | None = Form(default=None),
    engine: LegalEngine = Depends(get_legal_engine),
    audit_service: AuditService = Depends(get_audit_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> ContractAnalysisResponse:
    user_id = current_user.id if current_user else user_id
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
    current_user: User | None = Depends(get_optional_current_user),
) -> EvidenceAnalysisResponse:
    user_id = current_user.id if current_user else user_id
    response = await engine.analyze_evidence(evidence_file, evidence_text, user_id)
    audit_service.log("documents.evidence", {"filename": getattr(evidence_file, "filename", None)}, response.model_dump(), user_id)
    return response


@router.get("/templates", response_model=DocumentTemplateDirectoryResponse)
def list_document_templates(
    query: str | None = None,
    document_type: str | None = None,
    category: str | None = None,
    only_free: bool = False,
    mine_only: bool = False,
    limit: int = Query(default=24, ge=1, le=100),
    marketplace_service: DocumentMarketplaceService = Depends(get_document_marketplace_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> DocumentTemplateDirectoryResponse:
    return marketplace_service.list_templates(
        query=query,
        document_type=document_type,
        category=category,
        only_free=only_free,
        mine_only=mine_only,
        limit=limit,
        current_user=current_user,
    )


@router.get("/templates/{template_id}", response_model=DocumentTemplateDetailResponse)
def get_document_template(
    template_id: int,
    marketplace_service: DocumentMarketplaceService = Depends(get_document_marketplace_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> DocumentTemplateDetailResponse:
    return marketplace_service.get_template(template_id, current_user=current_user)


@router.post("/templates", response_model=DocumentTemplateDetailResponse, status_code=201)
async def create_document_template(
    title: str = Form(...),
    document_type: str = Form(...),
    category: str = Form(default="general"),
    description: str = Form(...),
    price_rupees: str = Form(default="0"),
    template_body: str | None = Form(default=None),
    fields_json: str = Form(...),
    tags_json: str | None = Form(default=None),
    sample_input_json: str | None = Form(default=None),
    is_published: bool = Form(default=True),
    template_file: UploadFile | None = File(default=None),
    marketplace_service: DocumentMarketplaceService = Depends(get_document_marketplace_service),
    audit_service: AuditService = Depends(get_audit_service),
    current_user: User = Depends(get_current_user),
) -> DocumentTemplateDetailResponse:
    try:
        fields = _parse_fields_json(fields_json)
        tags = _parse_tags_json(tags_json)
        sample_input = _parse_sample_input_json(sample_input_json)
    except ValueError as exc:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    response = await marketplace_service.create_template(
        title=title,
        document_type=document_type,
        category=category,
        description=description,
        price_rupees=price_rupees,
        template_body=template_body,
        fields=fields,
        tags=tags,
        sample_input=sample_input,
        is_published=is_published,
        template_file=template_file,
        current_user=current_user,
    )
    audit_service.log(
        "documents.template_publish",
        {
            "title": title,
            "document_type": document_type,
            "category": category,
            "price_rupees": price_rupees,
            "filename": getattr(template_file, "filename", None),
        },
        response.model_dump(mode="json"),
        current_user.id,
    )
    return response


@router.post("/templates/{template_id}/checkout", response_model=DocumentTemplateCheckoutResponse)
def checkout_document_template(
    template_id: int,
    payload: DocumentTemplateCheckoutRequest,
    marketplace_service: DocumentMarketplaceService = Depends(get_document_marketplace_service),
    audit_service: AuditService = Depends(get_audit_service),
    current_user: User = Depends(get_current_user),
) -> DocumentTemplateCheckoutResponse:
    response = marketplace_service.checkout_template(template_id, payload, current_user=current_user)
    audit_service.log(
        "documents.template_checkout",
        {"template_id": template_id, "answers": payload.answers},
        response.model_dump(mode="json"),
        current_user.id,
    )
    return response


@router.post("/orders/{order_id}/verify-payment", response_model=DocumentOrderDetailResponse)
def verify_document_payment(
    order_id: int,
    payload: DocumentPaymentVerificationRequest,
    marketplace_service: DocumentMarketplaceService = Depends(get_document_marketplace_service),
    audit_service: AuditService = Depends(get_audit_service),
    current_user: User = Depends(get_current_user),
) -> DocumentOrderDetailResponse:
    response = marketplace_service.verify_payment(order_id, payload, current_user=current_user)
    audit_service.log(
        "documents.template_verify_payment",
        {"order_id": order_id, "provider": payload.provider},
        response.model_dump(mode="json"),
        current_user.id,
    )
    return response


@router.get("/orders/mine", response_model=DocumentOrderListResponse)
def my_document_orders(
    limit: int = Query(default=25, ge=1, le=100),
    marketplace_service: DocumentMarketplaceService = Depends(get_document_marketplace_service),
    current_user: User = Depends(get_current_user),
) -> DocumentOrderListResponse:
    return marketplace_service.list_orders_for_user(current_user=current_user, limit=limit)


@router.get("/orders/{order_id}", response_model=DocumentOrderDetailResponse)
def get_document_order(
    order_id: int,
    marketplace_service: DocumentMarketplaceService = Depends(get_document_marketplace_service),
    current_user: User = Depends(get_current_user),
) -> DocumentOrderDetailResponse:
    return marketplace_service.get_order(order_id, current_user=current_user)
