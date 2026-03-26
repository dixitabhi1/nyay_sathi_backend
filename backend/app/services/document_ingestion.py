from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from fastapi import UploadFile

from app.core.config import Settings


class DocumentIngestionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def read_upload_bytes(self, upload: UploadFile) -> bytes:
        content = await upload.read()
        await upload.seek(0)
        return content

    async def save_upload(self, upload: UploadFile, content: bytes | None = None) -> Path:
        destination = self.settings.upload_dir / f"{uuid4()}_{upload.filename}"
        payload = content if content is not None else await self.read_upload_bytes(upload)
        destination.write_bytes(payload)
        return destination

    async def extract_text(self, upload: UploadFile, content: bytes | None = None) -> str:
        suffix = Path(upload.filename or "").suffix.lower()
        content_type = (upload.content_type or "").lower()
        payload = content if content is not None else await self.read_upload_bytes(upload)

        if suffix in {".txt", ".md"}:
            return payload.decode("utf-8", errors="ignore")
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(payload))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        if suffix == ".docx":
            from docx import Document

            document = Document(BytesIO(payload))
            return "\n".join(paragraph.text for paragraph in document.paragraphs)
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"} or content_type.startswith("image/"):
            from PIL import Image, UnidentifiedImageError
            import pytesseract

            try:
                image = Image.open(BytesIO(payload)).convert("RGB")
            except UnidentifiedImageError as exc:
                raise HTTPException(
                    status_code=422,
                    detail="NyayaSetu could not read the uploaded image. Please upload a clearer image, PDF, or use manual entry.",
                ) from exc
            try:
                text = pytesseract.image_to_string(image, lang=self.settings.ocr_language)
                if text.strip():
                    return text
                fallback = pytesseract.image_to_string(image, lang="eng")
                if fallback.strip():
                    return fallback
                raise HTTPException(
                    status_code=422,
                    detail="NyayaSetu could not extract readable text from this image. Please try a clearer scan or use manual entry.",
                )
            except pytesseract.TesseractNotFoundError as exc:
                raise HTTPException(
                    status_code=503,
                    detail="Image OCR is not available in this environment right now. Please try manual entry or upload a text/PDF complaint.",
                ) from exc
            except pytesseract.TesseractError:
                try:
                    fallback = pytesseract.image_to_string(image, lang="eng")
                    if fallback.strip():
                        return fallback
                except Exception:
                    pass
                raise HTTPException(
                    status_code=422,
                    detail="NyayaSetu could not process the uploaded image text reliably. Please try a clearer image or a PDF version.",
                )
        if suffix in {".mp3", ".wav", ".m4a", ".webm", ".ogg"} or content_type.startswith("audio/"):
            try:
                import whisper
            except ImportError as exc:
                raise HTTPException(
                    status_code=503,
                    detail="Audio transcription is not available in this environment right now. Please use the FIR mic transcription popup or paste the transcript text manually.",
                ) from exc

            try:
                temp_path = await self.save_upload(upload, content=payload)
                model = whisper.load_model(self.settings.whisper_model)
                transcript = model.transcribe(str(temp_path))
                text = str(transcript.get("text", "")).strip()
                if text:
                    return text
                raise HTTPException(
                    status_code=422,
                    detail="NyayaSetu could not detect enough speech from this recording. Please try a clearer voice note or use the transcript popup.",
                )
            except HTTPException:
                raise
            except FileNotFoundError as exc:
                raise HTTPException(
                    status_code=503,
                    detail="Audio transcription dependencies are missing in this environment. Please use the FIR mic transcription popup or enter transcript text manually.",
                ) from exc
            except RuntimeError as exc:
                raise HTTPException(
                    status_code=422,
                    detail="NyayaSetu could not transcribe this audio clip reliably. Please try a shorter clear recording, or use the mic transcription popup and review the transcript before submitting.",
                ) from exc
            except Exception as exc:
                raise HTTPException(
                    status_code=422,
                    detail="NyayaSetu could not process this audio file. Please try another recording format or use the transcript popup instead.",
                ) from exc
        return payload.decode("utf-8", errors="ignore")
