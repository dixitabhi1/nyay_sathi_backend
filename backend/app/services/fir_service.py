from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.db.session import SessionLocal
from app.models.fir import FIREvidence, FIRIntelligence, FIRRecord, FIRVersion
from app.schemas.fir import (
    AI_FIR_DISCLAIMER,
    FIRCompletenessResponse,
    FIRCrimePatternResponse,
    FIREvidenceAnalysisResponse,
    FIREvidenceItem,
    FIRDraftUpdateRequest,
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
from app.services.jurisdiction import JurisdictionService
from app.services.legal_section_classifier import LegalSectionClassifier


class FIRService:
    def __init__(
        self,
        document_ingestion: DocumentIngestionService,
        extraction_service: FIRExtractionService,
        classifier: LegalSectionClassifier,
        completeness_service: FIRCompletenessService,
        jurisdiction_service: JurisdictionService,
        evidence_intelligence: EvidenceIntelligenceService,
        crime_pattern_service: CrimePatternService,
    ) -> None:
        self.document_ingestion = document_ingestion
        self.extraction_service = extraction_service
        self.classifier = classifier
        self.completeness_service = completeness_service
        self.jurisdiction_service = jurisdiction_service
        self.evidence_intelligence = evidence_intelligence
        self.crime_pattern_service = crime_pattern_service

    def create_manual_fir(self, payload: FIRManualRequest) -> FIRRecordResponse:
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
        return self._persist_fir_record("manual", structured, None, payload.user_id)

    def preview_manual_fir(self, payload: FIRManualRequest) -> FIRUploadIntakeResponse:
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
        completeness = self.completeness_service.evaluate(structured)
        jurisdiction = self.jurisdiction_service.suggest(structured.incident_location or structured.police_station)
        score, score_reasons = self._score_fir(structured)
        draft = self._compose_draft(structured, sections, 1)
        return FIRUploadIntakeResponse(
            extracted_data=structured,
            transcript_text=None,
            cleaned_text=structured.incident_description,
            sections=sections,
            legal_reasoning=reasoning,
            jurisdiction=jurisdiction,
            completeness=completeness,
            case_strength_score=score,
            case_strength_reasoning=score_reasons,
            draft_text=draft,
        )

    async def create_fir_from_upload(
        self,
        complaint_file: UploadFile,
        police_station: str | None = None,
        user_id: str | None = None,
    ) -> FIRRecordResponse:
        saved_path = await self.document_ingestion.save_upload(complaint_file)
        extracted_text = await self.document_ingestion.extract_text(complaint_file)
        structured = self.extraction_service.extract_from_text(
            extracted_text,
            defaults={"police_station": police_station},
        )
        response = self._persist_fir_record("upload", structured, None, user_id)
        self._attach_saved_evidence(
            response.fir_id,
            complaint_file.filename or Path(saved_path).name,
            str(saved_path),
            complaint_file.content_type or "application/octet-stream",
        )
        return self.get_fir_record(response.fir_id)

    async def preview_uploaded_complaint(
        self,
        complaint_file: UploadFile,
        police_station: str | None = None,
    ) -> FIRUploadIntakeResponse:
        extracted_text = await self.document_ingestion.extract_text(complaint_file)
        cleaned_text = self.extraction_service.clean_text(extracted_text)
        structured = self.extraction_service.extract_from_text(cleaned_text, defaults={"police_station": police_station})
        sections, reasoning = self.classifier.classify(structured.incident_description)
        completeness = self.completeness_service.evaluate(structured)
        jurisdiction = self.jurisdiction_service.suggest(structured.incident_location or police_station)
        score, score_reasons = self._score_fir(structured)
        draft = self._compose_draft(structured, sections, 1)
        return FIRUploadIntakeResponse(
            extracted_data=structured,
            transcript_text=None,
            cleaned_text=cleaned_text,
            sections=sections,
            legal_reasoning=reasoning,
            jurisdiction=jurisdiction,
            completeness=completeness,
            case_strength_score=score,
            case_strength_reasoning=score_reasons,
            draft_text=draft,
        )

    async def create_fir_from_voice(
        self,
        audio_file: UploadFile | None = None,
        payload: FIRVoiceTranscriptRequest | None = None,
    ) -> FIRRecordResponse:
        transcript_text: str
        defaults: dict = {}
        user_id: str | None = None
        if payload:
            transcript_text = self.extraction_service.clean_text(payload.transcript_text)
            defaults = {
                "police_station": payload.police_station,
                "complainant_name": payload.complainant_name,
            }
            user_id = payload.user_id
        elif audio_file:
            saved_path = await self.document_ingestion.save_upload(audio_file)
            transcript_text = self.extraction_service.clean_text(await self.document_ingestion.extract_text(audio_file))
            defaults = {}
            user_id = None
            structured = self.extraction_service.extract_from_text(transcript_text, defaults=defaults)
            response = self._persist_fir_record("voice", structured, transcript_text, user_id)
            self._attach_saved_evidence(
                response.fir_id,
                audio_file.filename or Path(saved_path).name,
                str(saved_path),
                audio_file.content_type or "audio/webm",
            )
            return self.get_fir_record(response.fir_id)
        else:
            raise HTTPException(status_code=400, detail="Provide an audio file or transcript text.")

        structured = self.extraction_service.extract_from_text(transcript_text, defaults=defaults)
        return self._persist_fir_record("voice", structured, transcript_text, user_id)

    async def preview_voice_processing(
        self,
        audio_file: UploadFile | None = None,
        payload: FIRVoiceTranscriptRequest | None = None,
    ) -> FIRVoiceProcessingResponse:
        if payload:
            transcript_text = self.extraction_service.clean_text(payload.transcript_text)
            defaults = {
                "police_station": payload.police_station,
                "complainant_name": payload.complainant_name,
            }
        elif audio_file:
            transcript_text = self.extraction_service.clean_text(await self.document_ingestion.extract_text(audio_file))
            defaults = {}
        else:
            raise HTTPException(status_code=400, detail="Provide an audio file or transcript text.")

        extracted = self.extraction_service.extract_from_text(transcript_text, defaults=defaults)
        sections, _ = self.classifier.classify(extracted.incident_description)
        return FIRVoiceProcessingResponse(
            transcript_text=transcript_text,
            cleaned_text=transcript_text,
            extracted_data=extracted,
            sections=sections,
            jurisdiction=self.jurisdiction_service.suggest(extracted.incident_location),
            completeness=self.completeness_service.evaluate(extracted),
        )

    def get_fir_record(self, fir_id: str) -> FIRRecordResponse:
        session = SessionLocal()
        try:
            record = session.get(FIRRecord, fir_id)
            if not record:
                raise HTTPException(status_code=404, detail="FIR record not found.")
            evidence_rows = session.query(FIREvidence).filter(FIREvidence.fir_id == fir_id).order_by(FIREvidence.id.asc()).all()
            intelligence = session.get(FIRIntelligence, fir_id)
            return self._serialize_record(record, evidence_rows, intelligence)
        finally:
            session.close()

    def list_records(self, limit: int = 25) -> FIRRecordListResponse:
        session = SessionLocal()
        try:
            rows = session.query(FIRRecord).order_by(FIRRecord.last_edited_at.desc()).limit(limit).all()
            summaries: list[FIRRecordSummary] = []
            for row in rows:
                extracted = FIRStructuredData.model_validate_json(row.extracted_payload)
                summaries.append(
                    FIRRecordSummary(
                        fir_id=row.id,
                        workflow=row.workflow,
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

    def update_draft(self, fir_id: str, payload: FIRDraftUpdateRequest) -> FIRRecordResponse:
        session = SessionLocal()
        try:
            record = session.get(FIRRecord, fir_id)
            if not record:
                raise HTTPException(status_code=404, detail="FIR record not found.")
            next_version = record.current_version + 1
            now = datetime.utcnow()
            record.current_draft = payload.draft_text
            record.current_version = next_version
            record.updated_at = now
            record.last_edited_at = now
            session.add(
                FIRVersion(
                    fir_id=fir_id,
                    version_number=next_version,
                    draft_text=payload.draft_text,
                    edited_by=payload.edited_by,
                    edit_summary=payload.edit_summary,
                )
            )
            session.add(record)
            session.commit()
            evidence_rows = session.query(FIREvidence).filter(FIREvidence.fir_id == fir_id).order_by(FIREvidence.id.asc()).all()
            intelligence = session.get(FIRIntelligence, fir_id)
            return self._serialize_record(record, evidence_rows, intelligence)
        finally:
            session.close()

    def list_versions(self, fir_id: str) -> FIRVersionsResponse:
        session = SessionLocal()
        try:
            rows = session.query(FIRVersion).filter(FIRVersion.fir_id == fir_id).order_by(FIRVersion.version_number.asc()).all()
            return FIRVersionsResponse(
                fir_id=fir_id,
                versions=[
                    FIRVersionItem(
                        version_number=row.version_number,
                        draft_text=row.draft_text,
                        edited_by=row.edited_by,
                        edit_summary=row.edit_summary,
                        created_at=row.created_at.isoformat(),
                    )
                    for row in rows
                ],
            )
        finally:
            session.close()

    async def attach_evidence(self, fir_id: str, files: list[UploadFile]) -> FIRRecordResponse:
        for upload in files:
            saved_path = await self.document_ingestion.save_upload(upload)
            self._attach_saved_evidence(
                fir_id,
                upload.filename or Path(saved_path).name,
                str(saved_path),
                upload.content_type or "application/octet-stream",
            )
        return self.get_fir_record(fir_id)

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

    def intelligence_summary(self, fir_id: str) -> FIRIntelligenceResponse:
        record = self.get_fir_record(fir_id)
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
            crime_pattern=pattern,
        )

    def _persist_fir_record(
        self,
        workflow: str,
        structured: FIRStructuredData,
        transcript_text: str | None,
        user_id: str | None,
    ) -> FIRRecordResponse:
        sections, legal_reasoning = self.classifier.classify(structured.incident_description)
        completeness = self.completeness_service.evaluate(structured)
        jurisdiction = self.jurisdiction_service.suggest(structured.incident_location or structured.police_station)
        score, score_reasons = self._score_fir(structured)
        fir_id = uuid4().hex
        draft_text = self._compose_draft(structured, sections, 1)
        now = datetime.utcnow()
        record = FIRRecord(
            id=fir_id,
            workflow=workflow,
            status="draft",
            extracted_payload=structured.model_dump_json(),
            transcript_text=transcript_text,
            suggested_sections=json.dumps([section.model_dump() for section in sections], ensure_ascii=True),
            legal_reasoning=legal_reasoning,
            case_strength_score=score,
            case_strength_reasoning=json.dumps(score_reasons, ensure_ascii=True),
            disclaimer=AI_FIR_DISCLAIMER,
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
                    draft_text=draft_text,
                    edited_by=user_id,
                    edit_summary="Initial AI-generated FIR draft",
                )
            )
            session.commit()
            intelligence = session.get(FIRIntelligence, fir_id)
            return self._serialize_record(record, [], intelligence)
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
    ) -> FIRRecordResponse:
        extracted = FIRStructuredData.model_validate_json(record.extracted_payload)
        sections = [FIRSectionSuggestion.model_validate(item) for item in json.loads(record.suggested_sections)]
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
        return FIRRecordResponse(
            fir_id=record.id,
            workflow=record.workflow,
            status=record.status,
            extracted_data=extracted,
            transcript_text=record.transcript_text,
            sections=sections,
            legal_reasoning=record.legal_reasoning,
            draft_text=record.current_draft,
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

    def _compose_draft(self, structured: FIRStructuredData, sections, version: int) -> str:
        section_lines = "\n".join(f"- {section.section}: {section.title}" for section in sections)
        now_label = datetime.utcnow().strftime("%d %B %Y - %I:%M %p")
        return (
            "To\n"
            "Station House Officer\n"
            f"Police Station: {structured.police_station or '[Insert police station]'}\n\n"
            "Subject: Complaint regarding cognizable offence\n\n"
            "Respected Sir/Madam,\n\n"
            f"I, {structured.complainant_name or '[Insert complainant name]'}"
            f"{', child of ' + structured.parent_name if structured.parent_name else ''}, "
            f"resident of {structured.address or '[Insert address]'}, would like to report that on "
            f"{structured.incident_date or '[Insert date]'}"
            f"{' at ' + structured.incident_time if structured.incident_time else ''} near "
            f"{structured.incident_location or '[Insert incident location]'}, the following incident occurred:\n\n"
            f"{structured.incident_description}\n\n"
            f"Accused Details: {', '.join(structured.accused_details) or 'Not yet identified.'}\n"
            f"Witness Details: {', '.join(structured.witness_details) or 'No witness details provided yet.'}\n"
            f"Evidence Information: {', '.join(structured.evidence_information) or 'No evidence listed yet.'}\n\n"
            "Applicable Law:\n"
            f"{section_lines}\n\n"
            "Kindly register this complaint and take appropriate action.\n\n"
            f"Signature\n{structured.complainant_name or '[Insert complainant name]'}\n\n"
            f"Last Edited: {now_label}\n"
            f"Version: {version}.0\n\n"
            f"Disclaimer: {AI_FIR_DISCLAIMER}"
        )

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
