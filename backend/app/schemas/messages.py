from pydantic import BaseModel, Field


class MessageParticipantResponse(BaseModel):
    id: str
    full_name: str
    role: str
    email: str
    lawyer_handle: str | None = None
    lawyer_verified: bool = False


class MessageUserDirectoryResponse(BaseModel):
    users: list[MessageParticipantResponse]


class ConversationStartRequest(BaseModel):
    participant_id: str = Field(min_length=8, max_length=64)


class DirectMessageSendRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class DirectMessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender: MessageParticipantResponse
    recipient: MessageParticipantResponse
    content: str
    created_at: str
    read_at: str | None = None
    is_mine: bool


class ConversationSummaryResponse(BaseModel):
    id: int
    counterpart: MessageParticipantResponse
    last_message_preview: str | None = None
    last_message_at: str | None = None
    unread_count: int = 0


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummaryResponse]


class ConversationDetailResponse(BaseModel):
    conversation: ConversationSummaryResponse
    messages: list[DirectMessageResponse]
