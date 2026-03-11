from pydantic import BaseModel


class DatasetRefreshRequest(BaseModel):
    requested_by: str
    corpus_path: str | None = None


class DatasetRefreshResponse(BaseModel):
    accepted: bool
    message: str


class CorpusStatusResponse(BaseModel):
    total_documents: int
    total_chunks: int
    statute_chunks: int
    judgment_chunks: int
    mapping_rows: int
    languages: dict[str, int]
    target_statute_chunks: int = 10_000
    target_judgment_passages: int = 50_000
