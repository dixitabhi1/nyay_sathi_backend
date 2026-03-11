from pydantic import BaseModel


class UserHistoryItem(BaseModel):
    id: int
    action: str
    category: str
    title: str
    prompt_excerpt: str | None = None
    result_excerpt: str | None = None
    created_at: str


class UserHistoryResponse(BaseModel):
    items: list[UserHistoryItem]
