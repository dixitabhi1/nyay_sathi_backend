from datetime import datetime

from pydantic import BaseModel, Field


class ContractClause(BaseModel):
    heading: str
    content: str


class ContractRisk(BaseModel):
    severity: str
    issue: str
    recommendation: str


class ContractAnalysisResponse(BaseModel):
    summary: str
    clauses: list[ContractClause]
    risks: list[ContractRisk]
    missing_clauses: list[str]


class EvidenceEntity(BaseModel):
    label: str
    value: str


class EvidenceAnalysisResponse(BaseModel):
    extracted_text: str
    entities: list[EvidenceEntity]
    timeline: list[str]
    observations: list[str] = Field(default_factory=list)


class DocumentTemplateField(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    input_type: str = Field(default="text", min_length=3, max_length=32)
    placeholder: str | None = Field(default=None, max_length=255)
    help_text: str | None = Field(default=None, max_length=500)
    required: bool = True
    options: list[str] = Field(default_factory=list)


class DocumentTemplateSummaryResponse(BaseModel):
    id: int
    slug: str
    title: str
    document_type: str
    category: str
    description: str
    price_paise: int
    price_display: str
    currency: str
    is_free: bool
    uploaded_by_name: str
    uploaded_by_handle: str | None = None
    uploaded_by_role: str
    purchase_count: int
    buyer_count: int
    field_count: int
    tags: list[str] = Field(default_factory=list)
    preview_excerpt: str
    can_edit: bool = False
    has_access: bool = False
    created_at: datetime
    updated_at: datetime


class DocumentTemplateDetailResponse(DocumentTemplateSummaryResponse):
    fields: list[DocumentTemplateField] = Field(default_factory=list)
    sample_input: dict[str, str] = Field(default_factory=dict)
    template_body_preview: str
    payment_gateway_ready: bool = False


class DocumentTemplateDirectoryResponse(BaseModel):
    templates: list[DocumentTemplateSummaryResponse] = Field(default_factory=list)


class DocumentTemplateCheckoutRequest(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


class DocumentOrderSummaryResponse(BaseModel):
    id: int
    template_id: int
    template_title: str
    template_slug: str
    amount_paise: int
    amount_display: str
    payment_status: str
    payment_provider: str | None = None
    access_granted: bool
    generated_document_excerpt: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentOrderDetailResponse(DocumentOrderSummaryResponse):
    buyer_answers: dict[str, str] = Field(default_factory=dict)
    generated_document_text: str | None = None
    gateway_order_id: str | None = None


class DocumentOrderListResponse(BaseModel):
    orders: list[DocumentOrderSummaryResponse] = Field(default_factory=list)


class DocumentPaymentSessionResponse(BaseModel):
    provider: str
    public_key: str
    order_reference: str
    amount_paise: int
    currency: str
    business_name: str
    description: str
    buyer_email: str | None = None
    buyer_name: str | None = None


class DocumentTemplateCheckoutResponse(BaseModel):
    order: DocumentOrderDetailResponse
    payment_required: bool
    gateway_ready: bool
    checkout: DocumentPaymentSessionResponse | None = None
    message: str


class DocumentPaymentVerificationRequest(BaseModel):
    provider: str = Field(default="razorpay", min_length=2, max_length=64)
    payment_id: str = Field(min_length=4, max_length=128)
    order_reference: str = Field(min_length=4, max_length=128)
    signature: str = Field(min_length=8, max_length=512)
