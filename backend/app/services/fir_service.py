from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.auth import User
from app.models.fir import FIREvidence, FIRIntelligence, FIRRecord, FIRVersion
from app.schemas.fir import (
    AI_FIR_DISCLAIMER,
    FIRComparativeSectionsResponse,
    FIRCompletenessResponse,
    FIRCrimePatternResponse,
    FIREvidenceAnalysisResponse,
    FIREvidenceItem,
    FIRDraftUpdateRequest,
    FIRGeneratedDocument,
    FIRIntelligenceResponse,
    FIRJurisdictionSuggestion,
    FIRJurisdictionRequest,
    FIRManualRequest,
    FIRRecordListResponse,
    FIRRecordResponse,
    FIRRecordSummary,
    FIRSectionPredictionRequest,
    FIRSectionSuggestion,
    FIRStructuredData,
    FIRUploadIntakeResponse,
    FIRVersionItem,
    FIRVersionsResponse,
    FIRVoiceProcessingResponse,
    FIRVoiceTranscriptRequest,
)
from app.services.crime_pattern import CrimePatternService
from app.services.document_ingestion import DocumentIngestionService
from app.services.evidence_intelligence import EvidenceIntelligenceService
from app.services.fir_completeness import FIRCompletenessService
from app.services.fir_extraction import FIRExtractionService
from app.services.fir_generation import FIRGenerationService
from app.services.jurisdiction import JurisdictionService
from app.services.legal_section_classifier import LegalSectionClassifier


class FIRService:
    def __init__(
        self,
        settings: Settings,
        document_ingestion: DocumentIngestionService,
        extraction_service: FIRExtractionService,
        classifier: LegalSectionClassifier,
        generation_service: FIRGenerationService,
        completeness_service: FIRCompletenessService,
        jurisdiction_service: JurisdictionService,
        evidence_intelligence: EvidenceIntelligenceService,
        crime_pattern_service: CrimePatternService,
    ) -> None:
        self.settings = settings
        self.document_ingestion = document_ingestion
        self.extraction_service = extraction_service
        self.classifier = classifier
        self.generation_service = generation_service
        self.completeness_service = completeness_service
        self.jurisdiction_service = jurisdiction_service
        self.evidence_intelligence = evidence_intelligence
        self.crime_pattern_service = crime_pattern_service

    def create_manual_fir(self, payload: FIRManualRequest, viewer: User | None = None) -> FIRRecordResponse:
        self._ensure_document_kind_access(payload.draft_role, viewer)
        structured = FIRStructuredData(
            complainant_name=payload.complainant_name,
            parent_name=payload.parent_name,
            address=payload.address,
            contact_number=payload.contact_number,
            police_station=payload.police_station,
            incident_date=payload.incident_date,
            incident_time=payload.incident_time,
            incident_location=payload.incident_location,
            incident_description=payload.incident_description,
            accused_details=payload.accused_details,
            witness_details=payload.witness_details,
            evidence_information=payload.evidence_information,
        )
        return self._persist_fir_record(
            workflow="manual",
            structured=structured,
            transcript_text=None,
            user_id=payload.user_id,
            draft_role=payload.draft_role,
            draft_language=payload.language,
            source_application_text=None,
            viewer=viewer,
        )

    def preview_manual_fir(self, payload: FIRManualRequest, viewer: User | None = None) -> FIRUploadIntakeResponse:
        self._ensure_document_kind_access(payload.draft_role, viewer)
        structured = FIRStructuredData(
            complainant_name=payload.complainant_name,
            parent_name=payload.parent_name,
            address=payload.address,
            contact_number=payload.contact_number,
            police_station=payload.police_station,
            incident_date=payload.incident_date,
            incident_time=payload.incident_time,
            incident_location=payload.incident_location,
            incident_description=payload.incident_description,
            accused_details=payload.accused_details,
            witness_details=payload.witness_details,
            evidence_information=payload.evidence_information,
        )
        sections, reasoning = self.classifier.classify(structured.incident_description)
        comparative_sections = self.classifier.compare_sections(structured.incident_description, sections)
        completeness = self.completeness_service.evaluate(structured)
        jurisdiction = self.jurisdiction_service.suggest(structured.incident_location or structured.police_station)
        score, score_reasons = self._score_fir(structured)
        documents = self.generation_service.generate_document_bundle(
            structured,
            comparative_sections,
            language=payload.language,
            source_application_text=None,
        )
        _, draft, visible_documents = self._prepare_documents_for_viewer(documents, payload.draft_role, viewer)
        return FIRUploadIntakeResponse(
            extracted_data=structured,
            transcript_text=None,
            cleaned_text=structured.incident_description,
            sections=sections,
            comparative_sections=comparative_sections,
            legal_reasoning=reasoning,
            jurisdiction=jurisdiction,
            completeness=completeness,
            case_strength_score=score,
            case_strength_reasoning=score_reasons,
            draft_text=draft,
            generated_documents=visible_documents,
        )

    async def create_fir_from_upload(
        self,
        complaint_file: UploadFile,
        police_station: str | None = None,
        draft_role: str = "citizen_application",
        draft_language: str = "en",
        user_id: str | None = None,
        viewer: User | None = None,
    ) -> FIRRecordResponse:
        self._ensure_document_kind_access(draft_role, viewer)
        content = await self.document_ingestion.read_upload_bytes(complaint_file)
        saved_path = await self.document_ingestion.save_upload(complaint_file, content=content)
        extracted_text = await self.document_ingestion.extract_text(complaint_file, content=content)
        structured = self.extraction_service.extract_from_text(
            extracted_text,
            defaults={"police_station": police_station},
        )
        response = self._persist_fir_record(
            workflow="upload",
            structured=structured,
            transcript_text=None,
            user_id=user_id,
            draft_role=draft_role,
            draft_language=draft_language,
            source_application_text=extracted_text,
            viewer=viewer,
        )
        self._attach_saved_evidence(
            response.fir_id,
            complaint_file.filename or Path(saved_path).name,
            str(saved_path),
            complaint_file.content_type or "application/octet-stream",
        )
        return self.get_fir_record(response.fir_id, user_id=user_id, viewer=viewer)

    async def preview_uploaded_complaint(
        self,
        complaint_file: UploadFile,
        police_station: str | None = None,
        draft_role: str = "citizen_application",
        draft_language: str = "en",
        viewer: User | None = None,
    ) -> FIRUploadIntakeResponse:
        self._ensure_document_kind_access(draft_role, viewer)
        content = await self.document_ingestion.read_upload_bytes(complaint_file)
        extracted_text = await self.document_ingestion.extract_text(complaint_file, content=content)
        cleaned_text = self.extraction_service.clean_text(extracted_text)
        structured = self.extraction_service.extract_from_text(cleaned_text, defaults={"police_station": police_station})
        sections, reasoning = self.classifier.classify(structured.incident_description)
        comparative_sections = self.classifier.compare_sections(structured.incident_description, sections)
        completeness = self.completeness_service.evaluate(structured)
        jurisdiction = self.jurisdiction_service.suggest(structured.incident_location or police_station)
        score, score_reasons = self._score_fir(structured)
        documents = self.generation_service.generate_document_bundle(
            structured,
            comparative_sections,
            language=draft_language,
            source_application_text=cleaned_text,
        )
        _, draft, visible_documents = self._prepare_documents_for_viewer(documents, draft_role, viewer)
        return FIRUploadIntakeResponse(
            extracted_data=structured,
            transcript_text=None,
            cleaned_text=cleaned_text,
            sections=sections,
            comparative_sections=comparative_sections,
            legal_reasoning=reasoning,
            jurisdiction=jurisdiction,
            completeness=completeness,
            case_strength_score=score,
            case_strength_reasoning=score_reasons,
            draft_text=draft,
            generated_documents=visible_documents,
        )

    async def create_fir_from_voice(
        self,
        audio_file: UploadFile | None = None,
        payload: FIRVoiceTranscriptRequest | None = None,
        viewer: User | None = None,
    ) -> FIRRecordResponse:
        requested_kind = payload.draft_role if payload else "citizen_application"
        self._ensure_document_kind_access(requested_kind, viewer)
        defaults = {
            "police_station": payload.police_station if payload else None,
            "complainant_name": payload.complainant_name if payload else None,
        }
        user_id = payload.user_id if payload else None
        draft_role = payload.draft_role if payload else "citizen_application"
        draft_language = payload.language if payload else "en"
        transcript_candidate = self.extraction_service.clean_text(payload.transcript_text) if payload else ""

        saved_audio_path: Path | None = None
        saved_audio_media_type: str | None = None
        saved_audio_name: str | None = None

        if transcript_candidate:
            transcript_text = transcript_candidate
            if audio_file:
                audio_content = await self.document_ingestion.read_upload_bytes(audio_file)
                saved_audio_path = await self.document_ingestion.save_upload(audio_file, content=audio_content)
                saved_audio_media_type = audio_file.content_type or "audio/webm"
                saved_audio_name = audio_file.filename or Path(saved_audio_path).name
        elif audio_file:
            audio_content = await self.document_ingestion.read_upload_bytes(audio_file)
            saved_audio_path = await self.document_ingestion.save_upload(audio_file, content=audio_content)
            saved_audio_media_type = audio_file.content_type or "audio/webm"
            saved_audio_name = audio_file.filename or Path(saved_audio_path).name
            transcript_text = self.extraction_service.clean_text(
                await self.document_ingestion.extract_text(audio_file, content=audio_content)
            )
        else:
            raise HTTPException(status_code=400, detail="Provide an audio file or transcript text.")

        structured = self.extraction_service.extract_from_text(transcript_text, defaults=defaults)
        response = self._persist_fir_record(
            workflow="voice",
            structured=structured,
            transcript_text=transcript_text,
            user_id=user_id,
            draft_role=draft_role,
            draft_language=draft_language,
            source_application_text=transcript_text,
            viewer=viewer,
        )
        if saved_audio_path and saved_audio_name and saved_audio_media_type:
            self._attach_saved_evidence(
                response.fir_id,
                saved_audio_name,
                str(saved_audio_path),
                saved_audio_media_type,
            )
        return self.get_fir_record(response.fir_id, user_id=user_id, viewer=viewer)

    async def preview_voice_processing(
        self,
        audio_file: UploadFile | None = None,
        payload: FIRVoiceTranscriptRequest | None = None,
        viewer: User | None = None,
    ) -> FIRVoiceProcessingResponse:
        requested_kind = payload.draft_role if payload else "citizen_application"
        self._ensure_document_kind_access(requested_kind, viewer)
        defaults = {
            "police_station": payload.police_station if payload else None,
            "complainant_name": payload.complainant_name if payload else None,
        }
        transcript_candidate = self.extraction_service.clean_text(payload.transcript_text) if payload else ""

        if transcript_candidate:
            transcript_text = transcript_candidate
        elif audio_file:
            audio_content = await self.document_ingestion.read_upload_bytes(audio_file)
            transcript_text = self.extraction_service.clean_text(
                await self.document_ingestion.extract_text(audio_file, content=audio_content)
            )
        else:
            raise HTTPException(status_code=400, detail="Provide an audio file or transcript text.")

        extracted = self.extraction_service.extract_from_text(transcript_text, defaults=defaults)
        sections, _ = self.classifier.classify(extracted.incident_description)
        comparative_sections = self.classifier.compare_sections(extracted.incident_description, sections)
        documents = self.generation_service.generate_document_bundle(
            extracted,
            comparative_sections,
            language=payload.language if payload else "en",
            source_application_text=transcript_text,
        )
        _, _, visible_documents = self._prepare_documents_for_viewer(documents, requested_kind, viewer)
        return FIRVoiceProcessingResponse(
            transcript_text=transcript_text,
            cleaned_text=transcript_text,
            extracted_data=extracted,
            sections=sections,
            comparative_sections=comparative_sections,
            generated_documents=visible_documents,
            jurisdiction=self.jurisdiction_service.suggest(extracted.incident_location),
            completeness=self.completeness_service.evaluate(extracted),
        )

    def get_fir_record(self, fir_id: str, user_id: str | None = None, viewer: User | None = None) -> FIRRecordResponse:
        session = SessionLocal()
        try:
            record = session.get(FIRRecord, fir_id)
            if not record or (user_id and record.user_id and record.user_id != user_id):
                raise HTTPException(status_code=404, detail="FIR record not found.")
            evidence_rows = session.query(FIREvidence).filter(FIREvidence.fir_id == fir_id).order_by(FIREvidence.id.asc()).all()
            intelligence = session.get(FIRIntelligence, fir_id)
            return self._serialize_record(record, evidence_rows, intelligence, viewer=viewer)
        finally:
            session.close()

    def list_records(self, limit: int = 25, user_id: str | None = None) -> FIRRecordListResponse:
        session = SessionLocal()
        try:
            query = session.query(FIRRecord)
            if user_id:
                query = query.filter(FIRRecord.user_id == user_id)
            rows = query.order_by(FIRRecord.last_edited_at.desc()).limit(limit).all()
            summaries: list[FIRRecordSummary] = []
            for row in rows:
                extracted = FIRStructuredData.model_validate_json(row.extracted_payload)
                summaries.append(
                    FIRRecordSummary(
                        fir_id=row.id,
                        workflow=row.workflow,
                        draft_role=row.draft_role,
                        status=row.status,
                        complainant_name=extracted.complainant_name,
                        police_station=extracted.police_station,
                        incident_date=extracted.incident_date,
                        incident_location=extracted.incident_location,
                        case_strength_score=row.case_strength_score,
                        current_version=row.current_version,
                        last_edited_at=row.last_edited_at.isoformat(),
                        draft_excerpt=row.current_draft[:220],
                    )
                )
            return FIRRecordListResponse(records=summaries)
        finally:
            session.close()

    def update_draft(
        self,
        fir_id: str,
        payload: FIRDraftUpdateRequest,
        user_id: str | None = None,
        viewer: User | None = None,
    ) -> FIRRecordResponse:
        self._ensure_document_kind_access(payload.document_kind, viewer)
        session = SessionLocal()
        try:
            record = session.get(FIRRecord, fir_id)
            if not record or (user_id and record.user_id and record.user_id != user_id):
                raise HTTPException(status_code=404, detail="FIR record not found.")
            next_version = record.current_version + 1
            now = datetime.utcnow()
            document_kind = self._normalize_document_kind(payload.document_kind)
            draft_language = self._normalize_language(payload.language)
            self._set_document_content(record, document_kind, payload.draft_text)
            record.current_draft = payload.draft_text
            record.draft_role = document_kind
            record.draft_language = draft_language
            record.current_version = next_version
            record.updated_at = now
            record.last_edited_at = now
            session.add(
                FIRVersion(
                    fir_id=fir_id,
                    version_number=next_version,
                    document_kind=document_kind,
                    language=draft_language,
                    draft_text=payload.draft_text,
                    edited_by=payload.edited_by,
                    edit_summary=payload.edit_summary,
                )
            )
            session.add(record)
            session.commit()
            evidence_rows = session.query(FIREvidence).filter(FIREvidence.fir_id == fir_id).order_by(FIREvidence.id.asc()).all()
            intelligence = session.get(FIRIntelligence, fir_id)
            return self._serialize_record(record, evidence_rows, intelligence, viewer=viewer)
        finally:
            session.close()

    def list_versions(
        self,
        fir_id: str,
        user_id: str | None = None,
        viewer: User | None = None,
    ) -> FIRVersionsResponse:
        session = SessionLocal()
        try:
            record = session.get(FIRRecord, fir_id)
            if not record or (user_id and record.user_id and record.user_id != user_id):
                raise HTTPException(status_code=404, detail="FIR record not found.")
            rows = session.query(FIRVersion).filter(FIRVersion.fir_id == fir_id).order_by(FIRVersion.version_number.asc()).all()
            allowed_kinds = self._allowed_document_kinds_for_viewer(viewer)
            return FIRVersionsResponse(
                fir_id=fir_id,
                versions=[
                    FIRVersionItem(
                        version_number=row.version_number,
                        document_kind=row.document_kind,
                        language=row.language,
                        draft_text=row.draft_text,
                        edited_by=row.edited_by,
                        edit_summary=row.edit_summary,
                        created_at=row.created_at.isoformat(),
                    )
                    for row in rows
                    if row.document_kind in allowed_kinds
                ],
            )
        finally:
            session.close()

    async def attach_evidence(
        self,
        fir_id: str,
        files: list[UploadFile],
        user_id: str | None = None,
        viewer: User | None = None,
    ) -> FIRRecordResponse:
        self.get_fir_record(fir_id, user_id=user_id, viewer=viewer)
        for upload in files:
            saved_path = await self.document_ingestion.save_upload(upload)
            self._attach_saved_evidence(
                fir_id,
                upload.filename or Path(saved_path).name,
                str(saved_path),
                upload.content_type or "application/octet-stream",
            )
        return self.get_fir_record(fir_id, user_id=user_id, viewer=viewer)

    async def analyze_evidence(self, fir_id: str | None, files: list[UploadFile]) -> FIREvidenceAnalysisResponse:
        return await self.evidence_intelligence.analyze_uploads(files, fir_id)

    def predict_sections(self, payload: FIRSectionPredictionRequest) -> list[FIRSectionSuggestion]:
        sections, _ = self.classifier.classify(payload.incident_description)
        return sections

    def suggest_jurisdiction(self, payload: FIRJurisdictionRequest) -> FIRJurisdictionSuggestion | None:
        return self.jurisdiction_service.suggest(payload.incident_location)

    def evaluate_completeness(self, structured: FIRStructuredData) -> FIRCompletenessResponse:
        return self.completeness_service.evaluate(structured)

    def crime_patterns(self, window_days: int = 7) -> FIRCrimePatternResponse:
        return self.crime_pattern_service.get_patterns(window_days=window_days)

    def intelligence_summary(
        self,
        fir_id: str,
        user_id: str | None = None,
        viewer: User | None = None,
    ) -> FIRIntelligenceResponse:
        record = self.get_fir_record(fir_id, user_id=user_id, viewer=viewer)
        pattern = None
        if record.jurisdiction and record.jurisdiction.latitude is not None and record.jurisdiction.longitude is not None:
            nearby_count = self.crime_pattern_service.nearby_records(
                record.jurisdiction.latitude,
                record.jurisdiction.longitude,
                radius_km=1.0,
                window_days=7,
            )
            if nearby_count >= 2:
                hotspots = self.crime_pattern_service.get_patterns(window_days=7).hotspot_alerts
                pattern = hotspots[0] if hotspots else None
        return FIRIntelligenceResponse(
            fir_id=fir_id,
            jurisdiction=record.jurisdiction,
            completeness=record.completeness or self.completeness_service.evaluate(record.extracted_data),
            bns_prediction=record.sections,
            comparative_sections=record.comparative_sections,
            crime_pattern=pattern,
        )

    def render_document_pdf(
        self,
        fir_id: str,
        document_kind: str,
        user_id: str | None = None,
        language: str | None = None,
        viewer: User | None = None,
    ) -> tuple[str, bytes]:
        self._ensure_document_kind_access(document_kind, viewer)
        record = self.get_fir_record(fir_id, user_id=user_id, viewer=viewer)
        target_kind = self._normalize_document_kind(document_kind)
        target_language = self._normalize_language(language or record.draft_language)
        document = next((item for item in record.generated_documents if item.kind == target_kind and item.language == target_language), None)
        if document is None:
            document = next((item for item in record.generated_documents if item.kind == target_kind), None)
        if document is None:
            raise HTTPException(status_code=404, detail="Requested FIR document was not found.")
        pdf_bytes = self.generation_service.render_pdf(document.title, document.content, language=document.language)
        filename = f"{fir_id}-{target_kind}-{document.language}.pdf"
        return filename, pdf_bytes

    def _persist_fir_record(
        self,
        workflow: str,
        structured: FIRStructuredData,
        transcript_text: str | None,
        user_id: str | None,
        draft_role: str,
        draft_language: str,
        source_application_text: str | None,
        viewer: User | None,
    ) -> FIRRecordResponse:
        sections, legal_reasoning = self.classifier.classify(structured.incident_description)
        comparative_sections = self.classifier.compare_sections(structured.incident_description, sections)
        completeness = self.completeness_service.evaluate(structured)
        jurisdiction = self.jurisdiction_service.suggest(structured.incident_location or structured.police_station)
        score, score_reasons = self._score_fir(structured)
        fir_id = uuid4().hex
        normalized_draft_role = self._normalize_document_kind(draft_role)
        normalized_language = self._normalize_language(draft_language)
        documents = self.generation_service.generate_document_bundle(
            structured,
            comparative_sections,
            language=normalized_language,
            source_application_text=source_application_text,
        )
        draft_text = self._select_document_content(documents, normalized_draft_role)
        now = datetime.utcnow()
        record = FIRRecord(
            id=fir_id,
            workflow=workflow,
            draft_role=normalized_draft_role,
            draft_language=normalized_language,
            status="draft",
            extracted_payload=structured.model_dump_json(),
            transcript_text=transcript_text,
            suggested_sections=json.dumps([section.model_dump() for section in sections], ensure_ascii=True),
            comparative_sections=comparative_sections.model_dump_json(),
            legal_reasoning=legal_reasoning,
            case_strength_score=score,
            case_strength_reasoning=json.dumps(score_reasons, ensure_ascii=True),
            disclaimer=AI_FIR_DISCLAIMER,
            citizen_application_text=self._document_content(documents, "citizen_application"),
            police_fir_text=self._document_content(documents, "police_fir"),
            lawyer_analysis_text=self._document_content(documents, "lawyer_analysis"),
            source_application_text=source_application_text,
            current_draft=draft_text,
            current_version=1,
            user_id=user_id,
            created_at=now,
            updated_at=now,
            last_edited_at=now,
        )
        session = SessionLocal()
        try:
            session.add(record)
            session.add(
                FIRIntelligence(
                    fir_id=fir_id,
                    crime_category=sections[0].title if sections else "General Crime",
                    incident_location=structured.incident_location,
                    police_station=(jurisdiction.suggested_police_station if jurisdiction else structured.police_station),
                    district=(jurisdiction.district if jurisdiction else None),
                    state=(jurisdiction.state if jurisdiction else None),
                    latitude=(jurisdiction.latitude if jurisdiction else None),
                    longitude=(jurisdiction.longitude if jurisdiction else None),
                    completeness_score=completeness.completeness_score,
                    missing_fields=json.dumps(completeness.missing_fields, ensure_ascii=True),
                    jurisdiction_payload=(jurisdiction.model_dump_json() if jurisdiction else None),
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                FIRVersion(
                    fir_id=fir_id,
                    version_number=1,
                    document_kind=normalized_draft_role,
                    language=normalized_language,
                    draft_text=draft_text,
                    edited_by=user_id,
                    edit_summary="Initial AI-generated FIR draft",
                )
            )
            session.commit()
            intelligence = session.get(FIRIntelligence, fir_id)
            return self._serialize_record(record, [], intelligence, viewer=viewer)
        finally:
            session.close()

    def _attach_saved_evidence(self, fir_id: str, file_name: str, file_path: str, media_type: str) -> None:
        session = SessionLocal()
        try:
            record = session.get(FIRRecord, fir_id)
            if not record:
                raise HTTPException(status_code=404, detail="FIR record not found.")
            session.add(FIREvidence(fir_id=fir_id, file_name=file_name, file_path=file_path, media_type=media_type))
            record.updated_at = datetime.utcnow()
            session.add(record)
            session.commit()
        finally:
            session.close()

    def _serialize_record(
        self,
        record: FIRRecord,
        evidence_rows: list[FIREvidence],
        intelligence: FIRIntelligence | None,
        viewer: User | None = None,
    ) -> FIRRecordResponse:
        extracted = FIRStructuredData.model_validate_json(record.extracted_payload)
        sections = [FIRSectionSuggestion.model_validate(item) for item in json.loads(record.suggested_sections)]
        comparative_sections = (
            FIRComparativeSectionsResponse.model_validate_json(record.comparative_sections)
            if record.comparative_sections
            else None
        )
        score_reasons = json.loads(record.case_strength_reasoning)
        jurisdiction = (
            FIRJurisdictionSuggestion.model_validate_json(intelligence.jurisdiction_payload)
            if intelligence and intelligence.jurisdiction_payload
            else self.jurisdiction_service.suggest(extracted.incident_location)
        )
        completeness = (
            self.completeness_service.evaluate(extracted)
            if not intelligence or intelligence.completeness_score is None
            else FIRCompletenessResponse(
                completeness_score=intelligence.completeness_score,
                missing_fields=json.loads(intelligence.missing_fields or "[]"),
                suggestions=[
                    self.completeness_service._suggestion_for(field)
                    for field in json.loads(intelligence.missing_fields or "[]")
                ] or ["FIR contains the key details needed for preliminary review."],
            )
        )
        visible_draft_role, visible_draft_text, visible_documents = self._prepare_documents_for_viewer(
            self._serialize_documents(record),
            record.draft_role,
            viewer,
            fallback_content=record.current_draft,
        )
        return FIRRecordResponse(
            fir_id=record.id,
            workflow=record.workflow,
            draft_role=visible_draft_role,
            draft_language=record.draft_language,
            status=record.status,
            extracted_data=extracted,
            transcript_text=record.transcript_text,
            source_application_text=record.source_application_text,
            sections=sections,
            comparative_sections=comparative_sections,
            legal_reasoning=record.legal_reasoning,
            draft_text=visible_draft_text,
            generated_documents=visible_documents,
            jurisdiction=jurisdiction,
            completeness=completeness,
            case_strength_score=record.case_strength_score,
            case_strength_reasoning=score_reasons,
            evidence_items=[
                FIREvidenceItem(
                    evidence_id=row.id,
                    file_name=row.file_name,
                    file_path=row.file_path,
                    media_type=row.media_type,
                    uploaded_at=row.uploaded_at.isoformat(),
                )
                for row in evidence_rows
            ],
            current_version=record.current_version,
            last_edited_at=record.last_edited_at.isoformat(),
        )

    def _serialize_documents(self, record: FIRRecord) -> list[FIRGeneratedDocument]:
        documents: list[FIRGeneratedDocument] = []
        for kind, title, content in (
            ("citizen_application", "Citizen Complaint Application", record.citizen_application_text),
            ("police_fir", "Police FIR Draft", record.police_fir_text),
            ("lawyer_analysis", "Lawyer FIR Analysis", record.lawyer_analysis_text),
        ):
            if not content:
                continue
            documents.append(
                FIRGeneratedDocument(
                    kind=kind,
                    title=title,
                    language=record.draft_language,
                    content=content,
                    download_ready=(kind == "citizen_application"),
                )
            )
        if not documents and record.current_draft:
            documents.append(
                FIRGeneratedDocument(
                    kind=record.draft_role or "citizen_application",
                    title="FIR Draft",
                    language=record.draft_language or "en",
                    content=record.current_draft,
                    download_ready=(record.draft_role == "citizen_application"),
                )
            )
        return documents

    def _prepare_documents_for_viewer(
        self,
        documents: list[FIRGeneratedDocument],
        requested_kind: str,
        viewer: User | None,
        fallback_content: str | None = None,
    ) -> tuple[str, str, list[FIRGeneratedDocument]]:
        allowed_kinds = self._allowed_document_kinds_for_viewer(viewer)
        visible_documents = [document for document in documents if document.kind in allowed_kinds]
        if not visible_documents and documents:
            fallback_document = next((document for document in documents if document.kind == "citizen_application"), documents[0])
            visible_documents = [fallback_document]

        normalized_requested = self._normalize_document_kind(requested_kind)
        visible_default = next(
            (document for document in visible_documents if document.kind == normalized_requested),
            visible_documents[0] if visible_documents else None,
        )
        visible_kind = visible_default.kind if visible_default else normalized_requested
        visible_text = visible_default.content if visible_default else (fallback_content or "")
        return visible_kind, visible_text, visible_documents

    def _allowed_document_kinds_for_viewer(self, viewer: User | None) -> set[str]:
        if viewer and self._is_admin_viewer(viewer):
            return {"citizen_application", "police_fir", "lawyer_analysis"}
        if viewer and viewer.role == "police" and viewer.approval_status == "approved":
            return {"police_fir"}
        if viewer and viewer.role == "lawyer" and viewer.approval_status == "approved":
            return {"lawyer_analysis"}
        return {"citizen_application"}

    def _ensure_document_kind_access(self, document_kind: str, viewer: User | None) -> None:
        normalized = self._normalize_document_kind(document_kind)
        if normalized not in self._allowed_document_kinds_for_viewer(viewer):
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this FIR document track.",
            )

    def _is_admin_viewer(self, viewer: User) -> bool:
        return viewer.email.strip().lower() in self.settings.admin_email_allowlist or (
            viewer.role == "admin" and viewer.approval_status == "approved"
        )

    def _select_document_content(self, documents: list[FIRGeneratedDocument], draft_role: str) -> str:
        normalized = self._normalize_document_kind(draft_role)
        for item in documents:
            if item.kind == normalized:
                return item.content
        return documents[0].content if documents else ""

    def _document_content(self, documents: list[FIRGeneratedDocument], draft_role: str) -> str | None:
        normalized = self._normalize_document_kind(draft_role)
        for item in documents:
            if item.kind == normalized:
                return item.content
        return None

    def _set_document_content(self, record: FIRRecord, document_kind: str, content: str) -> None:
        if document_kind == "citizen_application":
            record.citizen_application_text = content
            return
        if document_kind == "police_fir":
            record.police_fir_text = content
            return
        if document_kind == "lawyer_analysis":
            record.lawyer_analysis_text = content
            return
        raise HTTPException(status_code=422, detail="Unsupported FIR document kind.")

    def _normalize_document_kind(self, document_kind: str) -> str:
        normalized = (document_kind or "citizen_application").strip().lower()
        allowed = {"citizen_application", "police_fir", "lawyer_analysis"}
        if normalized not in allowed:
            raise HTTPException(status_code=422, detail="FIR document kind must be citizen_application, police_fir, or lawyer_analysis.")
        return normalized

    def _normalize_language(self, language: str) -> str:
        normalized = (language or "en").strip().lower()
        return normalized if normalized in {"en", "hi"} else "en"

    def _score_fir(self, structured: FIRStructuredData) -> tuple[int, list[str]]:
        score = 40
        reasons: list[str] = []
        if structured.incident_description and len(structured.incident_description) >= 80:
            score += 12
            reasons.append("Incident description is sufficiently detailed.")
        elif structured.incident_description:
            score += 6
            reasons.append("Incident description is present but can be more specific.")
        if structured.incident_location:
            score += 10
            reasons.append("Location has been specified.")
        else:
            reasons.append("Location is missing.")
        if structured.incident_date:
            score += 10
            reasons.append("Incident date is available.")
        else:
            reasons.append("Incident date is missing.")
        if structured.incident_time:
            score += 5
            reasons.append("Incident time is available.")
        if structured.witness_details:
            score += 8
            reasons.append("Witness details strengthen the FIR.")
        else:
            reasons.append("No witness information provided.")
        if structured.evidence_information:
            score += 10
            reasons.append("Evidence details are attached or described.")
        else:
            reasons.append("No evidence information has been listed.")
        if structured.accused_details:
            score += 5
            reasons.append("Accused information is available.")
        score = max(0, min(score, 100))
        return score, reasons
