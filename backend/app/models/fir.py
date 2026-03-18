from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class FIRRecord(Base):
    __tablename__ = "fir_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workflow: Mapped[str] = mapped_column(String(32), nullable=False)
    draft_role: Mapped[str] = mapped_column(String(48), nullable=False, default="citizen_application")
    draft_language: Mapped[str] = mapped_column(String(32), nullable=False, default="en")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    extracted_payload: Mapped[str] = mapped_column(Text, nullable=False)
    transcript_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_sections: Mapped[str] = mapped_column(Text, nullable=False)
    comparative_sections: Mapped[str | None] = mapped_column(Text, nullable=True)
    legal_reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    case_strength_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    case_strength_reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    disclaimer: Mapped[str] = mapped_column(Text, nullable=False)
    citizen_application_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    police_fir_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    lawyer_analysis_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_application_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_draft: Mapped[str] = mapped_column(Text, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_edited_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class FIRVersion(Base):
    __tablename__ = "fir_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fir_id: Mapped[str] = mapped_column(String(64), ForeignKey("fir_records.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    document_kind: Mapped[str] = mapped_column(String(48), nullable=False, default="citizen_application")
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="en")
    draft_text: Mapped[str] = mapped_column(Text, nullable=False)
    edited_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    edit_summary: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class FIREvidence(Base):
    __tablename__ = "fir_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fir_id: Mapped[str] = mapped_column(String(64), ForeignKey("fir_records.id"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class FIRIntelligence(Base):
    __tablename__ = "fir_intelligence"

    fir_id: Mapped[str] = mapped_column(String(64), ForeignKey("fir_records.id"), primary_key=True)
    crime_category: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    incident_location: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    police_station: Mapped[str | None] = mapped_column(String(256), nullable=True)
    district: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    completeness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    missing_fields: Mapped[str | None] = mapped_column(Text, nullable=True)
    jurisdiction_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
