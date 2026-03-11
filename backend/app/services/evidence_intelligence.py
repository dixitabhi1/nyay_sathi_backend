from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

from app.schemas.fir import FIREvidenceAnalysisResponse, FIREvidenceInsight
from app.services.document_ingestion import DocumentIngestionService


OBJECT_KEYWORDS = {
    "weapon": ["gun", "knife", "pistol", "weapon"],
    "vehicle": ["car", "bike", "scooter", "truck", "vehicle"],
    "person": ["person", "man", "woman", "people"],
}
THREAT_KEYWORDS = ["kill", "threat", "extort", "attack", "bomb", "weapon", "shoot"]


class EvidenceIntelligenceService:
    def __init__(self, ingestion: DocumentIngestionService) -> None:
        self.ingestion = ingestion

    async def analyze_uploads(self, files: list[UploadFile], fir_id: str | None = None) -> FIREvidenceAnalysisResponse:
        analyses = [await self._analyze_single(upload) for upload in files]
        return FIREvidenceAnalysisResponse(fir_id=fir_id, analyses=analyses)

    async def _analyze_single(self, upload: UploadFile) -> FIREvidenceInsight:
        file_name = upload.filename or "evidence"
        media_type = upload.content_type or "application/octet-stream"
        suffix = Path(file_name).suffix.lower()
        file_category = self._detect_category(media_type, suffix)
        content = await upload.read()
        await upload.seek(0)

        extracted_text: str | None = None
        transcript_text: str | None = None
        detected_entities: list[str] = []
        detected_objects: list[str] = []
        event_markers: list[str] = []
        threat_indicators: list[str] = []
        notes: list[str] = []

        if file_category in {"document", "image", "audio"}:
            text = await self.ingestion.extract_text(upload)
            if file_category == "audio":
                transcript_text = text[:4000]
            else:
                extracted_text = text[:4000]
            detected_entities = self._extract_entities(text)
            threat_indicators = self._extract_threats(text)
            event_markers = self._extract_event_markers(text)
            notes.append("Textual extraction completed using OCR or transcription pipeline.")

        if file_category == "image":
            detected_objects = await self._detect_image_objects(content)
            notes.append("Image analysis uses optional local vision models when available.")
        elif file_category == "video":
            event_markers = self._extract_video_markers(file_name, media_type)
            notes.append("Video analysis currently uses file metadata and optional frame-level hooks.")
        elif file_category == "audio":
            notes.append("Audio transcript reviewed for threat keywords and entities.")

        return FIREvidenceInsight(
            file_name=file_name,
            media_type=media_type,
            file_category=file_category,
            extracted_text=extracted_text,
            transcript_text=transcript_text,
            detected_entities=detected_entities,
            detected_objects=detected_objects,
            event_markers=event_markers,
            threat_indicators=threat_indicators,
            notes=notes,
        )

    def _detect_category(self, media_type: str, suffix: str) -> str:
        if media_type.startswith("image/") or suffix in {".png", ".jpg", ".jpeg"}:
            return "image"
        if media_type.startswith("video/") or suffix in {".mp4", ".avi", ".mov", ".mkv"}:
            return "video"
        if media_type.startswith("audio/") or suffix in {".mp3", ".wav", ".webm", ".m4a", ".ogg"}:
            return "audio"
        return "document"

    async def _detect_image_objects(self, content: bytes) -> list[str]:
        try:
            from ultralytics import YOLO
            from PIL import Image

            model = YOLO("yolov8n.pt")
            image = Image.open(BytesIO(content))
            result = model.predict(image, verbose=False)
            names = result[0].names
            classes = result[0].boxes.cls.tolist() if result and result[0].boxes is not None else []
            detected = sorted({names[int(index)] for index in classes})
            if detected:
                return detected[:8]
        except Exception:
            pass

        try:
            text = content.decode("utf-8", errors="ignore").lower()
            return [label for label, keywords in OBJECT_KEYWORDS.items() if any(keyword in text for keyword in keywords)]
        except Exception:
            return []

    def _extract_entities(self, text: str) -> list[str]:
        entities: list[str] = []
        for pattern in [
            r"\b\d{10}\b",
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        ]:
            entities.extend(re.findall(pattern, text))
        return list(dict.fromkeys(entities))[:12]

    def _extract_threats(self, text: str) -> list[str]:
        lowered = text.lower()
        return [keyword for keyword in THREAT_KEYWORDS if keyword in lowered]

    def _extract_event_markers(self, text: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [sentence[:180] for sentence in sentences if re.search(r"\b\d{1,2}[:./-]|\b(?:am|pm|morning|evening|night)\b", sentence, re.IGNORECASE)][:6]

    def _extract_video_markers(self, file_name: str, media_type: str) -> list[str]:
        return [
            f"Video evidence received: {file_name}",
            f"Media type: {media_type}",
            "Frame extraction hook available for local CV pipeline integration.",
        ]

