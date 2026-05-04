import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.core.config import Settings
from app.core.dependencies import get_runtime_settings


router = APIRouter()


@router.get("/legal-metadata.json")
def get_legal_metadata_file(settings: Settings = Depends(get_runtime_settings)) -> FileResponse:
    metadata_path = settings.vector_metadata_path
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Legal metadata file was not found.")
    return FileResponse(metadata_path, media_type="application/json", filename="legal_metadata.json")


@router.get("/legal-metadata/summary")
def get_legal_metadata_summary(settings: Settings = Depends(get_runtime_settings)) -> dict:
    metadata_path = settings.vector_metadata_path
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Legal metadata file was not found.")

    with metadata_path.open("r", encoding="utf-8") as handle:
        records = json.load(handle)
    if not isinstance(records, list):
        raise HTTPException(status_code=422, detail="Legal metadata file is not a JSON array.")

    return {
        "file": str(metadata_path),
        "record_count": len(records),
        "sample": records[:5],
    }
