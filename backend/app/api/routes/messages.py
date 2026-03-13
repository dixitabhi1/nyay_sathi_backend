from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from app.core.dependencies import get_auth_service, get_messaging_service
from app.core.security import get_current_user
from app.models.auth import User
from app.schemas.messages import (
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationStartRequest,
    DirectMessageResponse,
    DirectMessageSendRequest,
    MessageUserDirectoryResponse,
)
from app.services.auth import AuthService
from app.services.messaging import MessagingService


router = APIRouter()


@router.get("/users", response_model=MessageUserDirectoryResponse)
def list_message_users(
    query: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    messaging_service: MessagingService = Depends(get_messaging_service),
    current_user: User = Depends(get_current_user),
) -> MessageUserDirectoryResponse:
    return messaging_service.list_user_directory(current_user=current_user, query=query, limit=limit)


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    messaging_service: MessagingService = Depends(get_messaging_service),
    current_user: User = Depends(get_current_user),
) -> ConversationListResponse:
    return messaging_service.list_conversations(current_user=current_user)


@router.post("/conversations", response_model=ConversationDetailResponse)
def start_conversation(
    payload: ConversationStartRequest,
    messaging_service: MessagingService = Depends(get_messaging_service),
    current_user: User = Depends(get_current_user),
) -> ConversationDetailResponse:
    return messaging_service.start_conversation(payload.participant_id, current_user=current_user)


@router.post("/lawyer/{handle}", response_model=ConversationDetailResponse)
def start_conversation_with_lawyer(
    handle: str,
    messaging_service: MessagingService = Depends(get_messaging_service),
    current_user: User = Depends(get_current_user),
) -> ConversationDetailResponse:
    return messaging_service.start_conversation_with_lawyer(handle, current_user=current_user)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: int,
    messaging_service: MessagingService = Depends(get_messaging_service),
    current_user: User = Depends(get_current_user),
) -> ConversationDetailResponse:
    return messaging_service.get_conversation(conversation_id, current_user=current_user)


@router.post("/conversations/{conversation_id}/messages", response_model=DirectMessageResponse)
async def send_message(
    conversation_id: int,
    payload: DirectMessageSendRequest,
    messaging_service: MessagingService = Depends(get_messaging_service),
    current_user: User = Depends(get_current_user),
) -> DirectMessageResponse:
    message = messaging_service.send_message(conversation_id, payload.content, current_user=current_user)
    await messaging_service.publish_message(message)
    return message


@router.websocket("/ws")
async def messages_ws(
    websocket: WebSocket,
    token: str,
    auth_service: AuthService = Depends(get_auth_service),
    messaging_service: MessagingService = Depends(get_messaging_service),
) -> None:
    user = auth_service.get_user_from_token(token)
    await messaging_service.connect(user.id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        messaging_service.disconnect(user.id, websocket)
