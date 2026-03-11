from pydantic import BaseModel, Field

from app.schemas.chat import SourceDocument


class ResearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    user_id: str | None = None


class ResearchResponse(BaseModel):
    summary: str
    hits: list[SourceDocument]

