from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DocumentTemplate(Base):
    __tablename__ = "document_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    lawyer_profile_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("lawyer_profiles.id"), nullable=True, index=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False, default="general")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    template_body: Mapped[str] = mapped_column(Text, nullable=False)
    field_schema_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    sample_input_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    preview_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_handle: Mapped[str | None] = mapped_column(String(64), nullable=True)
    owner_role: Mapped[str] = mapped_column(String(64), nullable=False, default="lawyer")
    price_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class DocumentOrder(Base):
    __tablename__ = "document_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("document_templates.id"), nullable=False, index=True)
    buyer_user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    payment_status: Mapped[str] = mapped_column(String(48), nullable=False, default="created")
    payment_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gateway_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    payment_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    buyer_answers_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    generated_document_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
