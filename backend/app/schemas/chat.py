from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class SourceDocument(BaseModel):
    title: str
    citation: str
    excerpt: str
    source_type: str
    score: float
    source_url: str | None = None
    reference_path: str | None = None
    retrieval_mode: str | None = None
    confidence: float | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    question: str = Field(min_length=5)
    language: str = "en"
    history: list[ChatMessage] = Field(default_factory=list)
    user_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    reasoning: str
    sources: list[SourceDocument]
    in_scope: bool = True
    scope_warning: str | None = None
    disclaimer: str = "This response is informational and should be reviewed by a qualified lawyer before acting on it."
