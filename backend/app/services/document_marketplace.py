from __future__ import annotations

import base64
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import hmac
import json
import re
from urllib import error as urllib_error
from urllib import request as urllib_request

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.auth import User
from app.models.documents import DocumentOrder, DocumentTemplate
from app.models.lawyer import LawyerProfile
from app.schemas.documents import (
    DocumentOrderDetailResponse,
    DocumentOrderListResponse,
    DocumentOrderSummaryResponse,
    DocumentPaymentSessionResponse,
    DocumentPaymentVerificationRequest,
    DocumentTemplateCheckoutRequest,
    DocumentTemplateCheckoutResponse,
    DocumentTemplateDetailResponse,
    DocumentTemplateDirectoryResponse,
    DocumentTemplateField,
    DocumentTemplateSummaryResponse,
)
from app.services.document_ingestion import DocumentIngestionService


PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")
ALLOWED_INPUT_TYPES = {"text", "textarea", "date", "number", "email", "phone", "select"}


class DocumentMarketplaceService:
    def __init__(self, settings: Settings, document_ingestion: DocumentIngestionService) -> None:
        self.settings = settings
        self.document_ingestion = document_ingestion

    def list_templates(
        self,
        query: str | None = None,
        document_type: str | None = None,
        category: str | None = None,
        only_free: bool = False,
        mine_only: bool = False,
        limit: int = 24,
        current_user: User | None = None,
    ) -> DocumentTemplateDirectoryResponse:
        if mine_only and not current_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to view your uploaded templates.")

        session = SessionLocal()
        try:
            db_query = session.query(DocumentTemplate).filter(DocumentTemplate.is_published.is_(True))
            if mine_only and current_user:
                db_query = db_query.filter(DocumentTemplate.owner_user_id == current_user.id)
            if document_type:
                db_query = db_query.filter(func.lower(DocumentTemplate.document_type) == document_type.strip().lower())
            if category:
                db_query = db_query.filter(func.lower(DocumentTemplate.category) == category.strip().lower())
            if only_free:
                db_query = db_query.filter(DocumentTemplate.price_paise <= 0)
            if query:
                pattern = f"%{query.strip().lower()}%"
                db_query = db_query.filter(
                    func.lower(DocumentTemplate.title).like(pattern)
                    | func.lower(DocumentTemplate.description).like(pattern)
                    | func.lower(DocumentTemplate.document_type).like(pattern)
                    | func.lower(DocumentTemplate.category).like(pattern)
                    | func.lower(DocumentTemplate.owner_display_name).like(pattern)
                    | func.lower(func.coalesce(DocumentTemplate.owner_handle, "")).like(pattern)
                    | func.lower(DocumentTemplate.tags_json).like(pattern)
                )

            rows = db_query.order_by(DocumentTemplate.updated_at.desc()).limit(limit).all()
            template_ids = [row.id for row in rows]
            purchase_counts, buyer_counts = self._template_stats(session, template_ids)
            accessible_ids = self._accessible_template_ids(session, current_user.id) if current_user else set()
            templates = [
                self._serialize_template_summary(
                    row,
                    purchase_count=purchase_counts.get(row.id, 0),
                    buyer_count=buyer_counts.get(row.id, 0),
                    current_user=current_user,
                    has_access=(row.id in accessible_ids),
                )
                for row in rows
            ]
            return DocumentTemplateDirectoryResponse(templates=templates)
        finally:
            session.close()

    def get_template(
        self,
        template_id: int,
        current_user: User | None = None,
    ) -> DocumentTemplateDetailResponse:
        session = SessionLocal()
        try:
            template = session.get(DocumentTemplate, template_id)
            if not template or (not template.is_published and not self._can_manage_template(current_user, template)):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document template not found.")
            purchase_counts, buyer_counts = self._template_stats(session, [template.id])
            accessible_ids = self._accessible_template_ids(session, current_user.id) if current_user else set()
            return self._serialize_template_detail(
                template,
                purchase_count=purchase_counts.get(template.id, 0),
                buyer_count=buyer_counts.get(template.id, 0),
                current_user=current_user,
                has_access=(template.id in accessible_ids),
            )
        finally:
            session.close()

    async def create_template(
        self,
        *,
        title: str,
        document_type: str,
        category: str,
        description: str,
        price_rupees: str,
        template_body: str | None,
        fields: list[DocumentTemplateField],
        tags: list[str],
        sample_input: dict[str, str],
        is_published: bool,
        template_file: UploadFile | None,
        current_user: User,
    ) -> DocumentTemplateDetailResponse:
        self._ensure_can_publish(current_user)
        resolved_body = (template_body or "").strip()
        if template_file is not None:
            file_content = await self.document_ingestion.read_upload_bytes(template_file)
            extracted = await self.document_ingestion.extract_text(template_file, content=file_content)
            resolved_body = extracted.strip() or resolved_body
        if not resolved_body:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Upload a lawyer template file or paste the template text.",
            )

        normalized_fields = self._normalize_fields(fields)
        normalized_tags = self._normalize_tags(tags)
        normalized_sample_input = self._normalize_sample_input(sample_input, normalized_fields)
        normalized_price = self._normalize_price_paise(price_rupees)

        session = SessionLocal()
        try:
            lawyer_profile = self._load_owner_profile(session, current_user.id)
            template = DocumentTemplate(
                owner_user_id=current_user.id,
                lawyer_profile_id=lawyer_profile.id if lawyer_profile else None,
                slug=self._unique_slug(session, title),
                title=title.strip(),
                document_type=document_type.strip(),
                category=(category.strip() or "general"),
                description=description.strip(),
                template_body=resolved_body,
                field_schema_json=json.dumps([field.model_dump() for field in normalized_fields], ensure_ascii=True),
                sample_input_json=json.dumps(normalized_sample_input, ensure_ascii=True),
                tags_json=json.dumps(normalized_tags, ensure_ascii=True),
                preview_excerpt=self._preview_excerpt(resolved_body),
                owner_display_name=(lawyer_profile.name if lawyer_profile else current_user.full_name.strip()),
                owner_handle=(lawyer_profile.handle if lawyer_profile else None),
                owner_role=("lawyer" if current_user.role == "lawyer" else "admin"),
                price_paise=normalized_price,
                currency="INR",
                is_published=is_published,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(template)
            session.commit()
            session.refresh(template)
            return self._serialize_template_detail(
                template,
                purchase_count=0,
                buyer_count=0,
                current_user=current_user,
                has_access=True,
            )
        finally:
            session.close()

    def checkout_template(
        self,
        template_id: int,
        payload: DocumentTemplateCheckoutRequest,
        current_user: User,
    ) -> DocumentTemplateCheckoutResponse:
        session = SessionLocal()
        try:
            template = session.get(DocumentTemplate, template_id)
            if not template or not template.is_published:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document template not found.")
            fields = self._load_fields(template)
            answers = self._normalize_answers(payload.answers, fields)
            generated_document = self._render_document(template.template_body, answers)
            now = datetime.utcnow()

            if template.price_paise <= 0:
                order = DocumentOrder(
                    template_id=template.id,
                    buyer_user_id=current_user.id,
                    amount_paise=0,
                    currency=template.currency,
                    payment_status="free_unlocked",
                    payment_provider="free",
                    access_granted=True,
                    buyer_answers_json=json.dumps(answers, ensure_ascii=True),
                    generated_document_text=generated_document,
                    created_at=now,
                    updated_at=now,
                )
                session.add(order)
                session.commit()
                session.refresh(order)
                return DocumentTemplateCheckoutResponse(
                    order=self._serialize_order_detail(order, template),
                    payment_required=False,
                    gateway_ready=False,
                    checkout=None,
                    message="This template is free. Your filled document is unlocked immediately.",
                )

            provider = self._payment_provider()
            if provider != "razorpay":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Paid document checkout is ready, but the payment gateway is not configured yet. Free templates still work.",
                )

            gateway_order = self._create_razorpay_order(
                amount_paise=template.price_paise,
                receipt=f"doc-{template.id}-{current_user.id[:12]}-{int(now.timestamp())}",
                notes={
                    "template_id": str(template.id),
                    "buyer_user_id": current_user.id,
                },
            )
            order = DocumentOrder(
                template_id=template.id,
                buyer_user_id=current_user.id,
                amount_paise=template.price_paise,
                currency=template.currency,
                payment_status="awaiting_payment",
                payment_provider="razorpay",
                gateway_order_id=gateway_order["id"],
                access_granted=False,
                buyer_answers_json=json.dumps(answers, ensure_ascii=True),
                generated_document_text=generated_document,
                created_at=now,
                updated_at=now,
            )
            session.add(order)
            session.commit()
            session.refresh(order)
            return DocumentTemplateCheckoutResponse(
                order=self._serialize_order_detail(order, template),
                payment_required=True,
                gateway_ready=True,
                checkout=DocumentPaymentSessionResponse(
                    provider="razorpay",
                    public_key=self.settings.razorpay_key_id,
                    order_reference=gateway_order["id"],
                    amount_paise=template.price_paise,
                    currency=template.currency,
                    business_name="NyayaSetu",
                    description=f"{template.title} by {template.owner_display_name}",
                    buyer_email=current_user.email,
                    buyer_name=current_user.full_name,
                ),
                message="Complete the payment to unlock the filled document.",
            )
        finally:
            session.close()

    def verify_payment(
        self,
        order_id: int,
        payload: DocumentPaymentVerificationRequest,
        current_user: User,
    ) -> DocumentOrderDetailResponse:
        session = SessionLocal()
        try:
            order = session.get(DocumentOrder, order_id)
            if not order or order.buyer_user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document order not found.")
            template = session.get(DocumentTemplate, order.template_id)
            if not template:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document template not found.")
            if order.access_granted:
                return self._serialize_order_detail(order, template)
            if payload.provider.strip().lower() != "razorpay" or self._payment_provider() != "razorpay":
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported payment verification provider.")
            if order.gateway_order_id != payload.order_reference:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment order reference does not match this document order.")
            expected_signature = hmac.new(
                self.settings.razorpay_key_secret.encode("utf-8"),
                f"{payload.order_reference}|{payload.payment_id}".encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected_signature, payload.signature):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment signature verification failed.")

            order.payment_status = "paid_unlocked"
            order.payment_provider = "razorpay"
            order.payment_id = payload.payment_id
            order.payment_signature = payload.signature
            order.access_granted = True
            order.updated_at = datetime.utcnow()
            session.add(order)
            session.commit()
            session.refresh(order)
            return self._serialize_order_detail(order, template)
        finally:
            session.close()

    def list_orders_for_user(self, current_user: User, limit: int = 25) -> DocumentOrderListResponse:
        session = SessionLocal()
        try:
            rows = (
                session.query(DocumentOrder, DocumentTemplate)
                .join(DocumentTemplate, DocumentTemplate.id == DocumentOrder.template_id)
                .filter(DocumentOrder.buyer_user_id == current_user.id)
                .order_by(DocumentOrder.updated_at.desc())
                .limit(limit)
                .all()
            )
            return DocumentOrderListResponse(
                orders=[self._serialize_order_summary(order, template) for order, template in rows]
            )
        finally:
            session.close()

    def get_order(self, order_id: int, current_user: User) -> DocumentOrderDetailResponse:
        session = SessionLocal()
        try:
            order = session.get(DocumentOrder, order_id)
            if not order or order.buyer_user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document order not found.")
            template = session.get(DocumentTemplate, order.template_id)
            if not template:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document template not found.")
            return self._serialize_order_detail(order, template)
        finally:
            session.close()

    def _template_stats(self, session, template_ids: list[int]) -> tuple[dict[int, int], dict[int, int]]:
        if not template_ids:
            return {}, {}
        purchase_rows = (
            session.query(DocumentOrder.template_id, func.count(DocumentOrder.id))
            .filter(DocumentOrder.template_id.in_(template_ids), DocumentOrder.access_granted.is_(True))
            .group_by(DocumentOrder.template_id)
            .all()
        )
        buyer_rows = (
            session.query(DocumentOrder.template_id, func.count(func.distinct(DocumentOrder.buyer_user_id)))
            .filter(DocumentOrder.template_id.in_(template_ids), DocumentOrder.access_granted.is_(True))
            .group_by(DocumentOrder.template_id)
            .all()
        )
        return (
            {template_id: count for template_id, count in purchase_rows},
            {template_id: count for template_id, count in buyer_rows},
        )

    def _accessible_template_ids(self, session, user_id: str | None) -> set[int]:
        if not user_id:
            return set()
        rows = (
            session.query(DocumentOrder.template_id)
            .filter(DocumentOrder.buyer_user_id == user_id, DocumentOrder.access_granted.is_(True))
            .all()
        )
        return {template_id for (template_id,) in rows}

    def _load_owner_profile(self, session, user_id: str) -> LawyerProfile | None:
        return (
            session.query(LawyerProfile)
            .filter(LawyerProfile.user_id == user_id)
            .order_by(LawyerProfile.created_at.desc())
            .first()
        )

    def _serialize_template_summary(
        self,
        template: DocumentTemplate,
        *,
        purchase_count: int,
        buyer_count: int,
        current_user: User | None,
        has_access: bool,
    ) -> DocumentTemplateSummaryResponse:
        tags = self._load_json_list(template.tags_json)
        return DocumentTemplateSummaryResponse(
            id=template.id,
            slug=template.slug,
            title=template.title,
            document_type=template.document_type,
            category=template.category,
            description=template.description,
            price_paise=template.price_paise,
            price_display=self._price_display(template.price_paise),
            currency=template.currency,
            is_free=template.price_paise <= 0,
            uploaded_by_name=template.owner_display_name,
            uploaded_by_handle=template.owner_handle,
            uploaded_by_role=template.owner_role,
            purchase_count=purchase_count,
            buyer_count=buyer_count,
            field_count=len(self._load_fields(template)),
            tags=tags,
            preview_excerpt=template.preview_excerpt or self._preview_excerpt(template.template_body),
            can_edit=self._can_manage_template(current_user, template),
            has_access=has_access or self._can_manage_template(current_user, template),
            created_at=template.created_at,
            updated_at=template.updated_at,
        )

    def _serialize_template_detail(
        self,
        template: DocumentTemplate,
        *,
        purchase_count: int,
        buyer_count: int,
        current_user: User | None,
        has_access: bool,
    ) -> DocumentTemplateDetailResponse:
        summary = self._serialize_template_summary(
            template,
            purchase_count=purchase_count,
            buyer_count=buyer_count,
            current_user=current_user,
            has_access=has_access,
        )
        return DocumentTemplateDetailResponse(
            **summary.model_dump(),
            fields=self._load_fields(template),
            sample_input=self._load_json_object(template.sample_input_json),
            template_body_preview=template.template_body[:1400],
            payment_gateway_ready=(self._payment_provider() == "razorpay"),
        )

    def _serialize_order_summary(self, order: DocumentOrder, template: DocumentTemplate) -> DocumentOrderSummaryResponse:
        document_text = order.generated_document_text if order.access_granted else None
        excerpt = self._preview_excerpt(document_text or template.preview_excerpt or template.template_body)
        return DocumentOrderSummaryResponse(
            id=order.id,
            template_id=template.id,
            template_title=template.title,
            template_slug=template.slug,
            amount_paise=order.amount_paise,
            amount_display=self._price_display(order.amount_paise),
            payment_status=order.payment_status,
            payment_provider=order.payment_provider,
            access_granted=order.access_granted,
            generated_document_excerpt=excerpt,
            created_at=order.created_at,
            updated_at=order.updated_at,
        )

    def _serialize_order_detail(self, order: DocumentOrder, template: DocumentTemplate) -> DocumentOrderDetailResponse:
        summary = self._serialize_order_summary(order, template)
        return DocumentOrderDetailResponse(
            **summary.model_dump(),
            buyer_answers=self._load_json_object(order.buyer_answers_json),
            generated_document_text=order.generated_document_text if order.access_granted else None,
            gateway_order_id=order.gateway_order_id,
        )

    def _normalize_fields(self, fields: list[DocumentTemplateField]) -> list[DocumentTemplateField]:
        normalized: list[DocumentTemplateField] = []
        seen_keys: set[str] = set()
        for field in fields:
            key = self._normalize_field_key(field.key or field.label)
            if not key or key in seen_keys:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Each document field needs a unique key.",
                )
            input_type = field.input_type.strip().lower() if field.input_type else "text"
            if input_type not in ALLOWED_INPUT_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Unsupported field type '{input_type}'.",
                )
            seen_keys.add(key)
            normalized.append(
                DocumentTemplateField(
                    key=key,
                    label=field.label.strip(),
                    input_type=input_type,
                    placeholder=(field.placeholder.strip() if field.placeholder else None),
                    help_text=(field.help_text.strip() if field.help_text else None),
                    required=field.required,
                    options=[option.strip() for option in field.options if option.strip()],
                )
            )
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Add at least one fillable field for the document template.",
            )
        return normalized

    def _normalize_sample_input(
        self,
        sample_input: dict[str, str],
        fields: list[DocumentTemplateField],
    ) -> dict[str, str]:
        allowed_keys = {field.key for field in fields}
        normalized: dict[str, str] = {}
        for key, value in (sample_input or {}).items():
            normalized_key = self._normalize_field_key(key)
            if normalized_key not in allowed_keys:
                continue
            normalized[normalized_key] = str(value).strip()
        for field in fields:
            normalized.setdefault(field.key, field.placeholder or field.label)
        return normalized

    def _normalize_answers(
        self,
        answers: dict[str, str],
        fields: list[DocumentTemplateField],
    ) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for field in fields:
            value = str((answers or {}).get(field.key, "")).strip()
            if field.required and not value:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{field.label} is required to generate this document.",
                )
            normalized[field.key] = value
        return normalized

    def _load_fields(self, template: DocumentTemplate) -> list[DocumentTemplateField]:
        try:
            raw_fields = json.loads(template.field_schema_json or "[]")
            return [DocumentTemplateField.model_validate(item) for item in raw_fields]
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Stored document field schema is invalid.") from exc

    def _load_json_list(self, raw: str | None) -> list[str]:
        try:
            data = json.loads(raw or "[]")
            if isinstance(data, list):
                return [str(item).strip() for item in data if str(item).strip()]
        except Exception:
            return []
        return []

    def _load_json_object(self, raw: str | None) -> dict[str, str]:
        try:
            data = json.loads(raw or "{}")
            if isinstance(data, dict):
                return {str(key): str(value) for key, value in data.items()}
        except Exception:
            return {}
        return {}

    def _normalize_tags(self, tags: list[str]) -> list[str]:
        normalized: list[str] = []
        for tag in tags:
            clean = tag.strip()
            if clean and clean.lower() not in {item.lower() for item in normalized}:
                normalized.append(clean)
        return normalized[:8]

    def _normalize_price_paise(self, price_rupees: str) -> int:
        try:
            amount = Decimal((price_rupees or "0").strip() or "0")
        except InvalidOperation as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter a valid document price.") from exc
        if amount < 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Document price cannot be negative.")
        return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    def _normalize_field_key(self, raw: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", (raw or "").strip().lower()).strip("_")
        return normalized[:80]

    def _preview_excerpt(self, text: str | None) -> str:
        compact = re.sub(r"\s+", " ", (text or "").strip())
        return compact[:280] if compact else "Template preview will appear here after the lawyer uploads the draft."

    def _price_display(self, price_paise: int) -> str:
        if price_paise <= 0:
            return "Free"
        rupees = price_paise / 100
        if rupees.is_integer():
            return f"₹{int(rupees):,}"
        return f"₹{rupees:,.2f}"

    def _ensure_can_publish(self, current_user: User) -> None:
        if self._is_admin_user(current_user):
            return
        if current_user.role == "lawyer" and current_user.approval_status == "approved":
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only approved lawyers or admins can publish document templates.",
        )

    def _can_manage_template(self, current_user: User | None, template: DocumentTemplate) -> bool:
        if not current_user:
            return False
        return template.owner_user_id == current_user.id or self._is_admin_user(current_user)

    def _is_admin_user(self, current_user: User) -> bool:
        return current_user.email.strip().lower() in self.settings.admin_email_allowlist or (
            current_user.role == "admin" and current_user.approval_status == "approved"
        )

    def _unique_slug(self, session, title: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", title.strip().lower()).strip("-") or "legal-document"
        candidate = base[:140]
        suffix = 1
        while session.query(DocumentTemplate).filter(DocumentTemplate.slug == candidate).first():
            suffix += 1
            candidate = f"{base[:130]}-{suffix}"
        return candidate

    def _render_document(self, template_body: str, answers: dict[str, str]) -> str:
        used_placeholder = False

        def replacement(match: re.Match[str]) -> str:
            nonlocal used_placeholder
            key = self._normalize_field_key(match.group(1))
            if key in answers:
                used_placeholder = True
                return answers.get(key, "")
            return ""

        rendered = PLACEHOLDER_PATTERN.sub(replacement, template_body)
        if not used_placeholder and answers:
            details_block = "\n".join(
                f"{key.replace('_', ' ').title()}: {value}"
                for key, value in answers.items()
                if value
            )
            if details_block:
                rendered = f"{rendered.strip()}\n\nProvided Details\n{details_block}".strip()
        return rendered.strip()

    def _payment_provider(self) -> str:
        provider = (self.settings.payment_provider or "none").strip().lower()
        if provider == "razorpay" and self.settings.razorpay_key_id and self.settings.razorpay_key_secret:
            return "razorpay"
        return "none"

    def _create_razorpay_order(
        self,
        *,
        amount_paise: int,
        receipt: str,
        notes: dict[str, str],
    ) -> dict:
        credentials = f"{self.settings.razorpay_key_id}:{self.settings.razorpay_key_secret}".encode("utf-8")
        payload = json.dumps(
            {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": receipt[:40],
                "notes": notes,
            }
        ).encode("utf-8")
        request = urllib_request.Request(
            "https://api.razorpay.com/v1/orders",
            data=payload,
            headers={
                "Authorization": f"Basic {base64.b64encode(credentials).decode('utf-8')}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Razorpay order creation failed: {detail or exc.reason}",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to reach Razorpay right now. Please try again shortly.",
            ) from exc
