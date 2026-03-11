from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings


class DocumentIngestionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def save_upload(self, upload: UploadFile) -> Path:
        destination = self.settings.upload_dir / f"{uuid4()}_{upload.filename}"
        content = await upload.read()
        destination.write_bytes(content)
        await upload.seek(0)
        return destination

    async def extract_text(self, upload: UploadFile) -> str:
        suffix = Path(upload.filename or "").suffix.lower()
        content_type = (upload.content_type or "").lower()
        content = await upload.read()
        await upload.seek(0)

        if suffix in {".txt", ".md"}:
            return content.decode("utf-8", errors="ignore")
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        if suffix == ".docx":
            from docx import Document

            document = Document(BytesIO(content))
            return "\n".join(paragraph.text for paragraph in document.paragraphs)
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"} or content_type.startswith("image/"):
            from PIL import Image
            import pytesseract

            image = Image.open(BytesIO(content))
            return pytesseract.image_to_string(image, lang=self.settings.ocr_language)
        if suffix in {".mp3", ".wav", ".m4a", ".webm", ".ogg"}:
            import whisper

            temp_path = await self.save_upload(upload)
            model = whisper.load_model(self.settings.whisper_model)
            transcript = model.transcribe(str(temp_path))
            return transcript["text"]
        return content.decode("utf-8", errors="ignore")
