from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from fastapi import HTTPException, WebSocket, status
from sqlalchemy import func, or_

from app.db.session import SessionLocal
from app.models.auth import User
from app.models.lawyer import LawyerProfile
from app.models.messaging import DirectConversation, DirectMessage
from app.schemas.messages import (
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationSummaryResponse,
    DirectMessageResponse,
    MessageParticipantResponse,
    MessageUserDirectoryResponse,
)


class MessagingService:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[user_id].add(websocket)
        await websocket.send_json({"type": "connection.ready", "payload": {"user_id": user_id}})

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        sockets = self._connections.get(user_id)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            self._connections.pop(user_id, None)

    async def publish_event(self, user_id: str, event_type: str, payload: dict) -> None:
        stale: list[WebSocket] = []
        for websocket in self._connections.get(user_id, set()):
            try:
                await websocket.send_json({"type": event_type, "payload": payload})
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(user_id, websocket)

    async def publish_message(self, message: DirectMessageResponse) -> None:
        payload = message.model_dump()
        await self.publish_event(message.sender.id, "message.new", payload)
        await self.publish_event(message.recipient.id, "message.new", payload)

    def list_user_directory(
        self,
        current_user: User,
        query: str | None = None,
        limit: int = 20,
    ) -> MessageUserDirectoryResponse:
        session = SessionLocal()
        try:
            db_query = (
                session.query(User, LawyerProfile)
                .outerjoin(LawyerProfile, LawyerProfile.user_id == User.id)
                .filter(User.is_active.is_(True), User.id != current_user.id)
            )
            if query:
                pattern = f"%{query.strip().lower()}%"
                db_query = db_query.filter(
                    or_(
                        func.lower(User.full_name).like(pattern),
                        func.lower(User.email).like(pattern),
                        func.lower(User.role).like(pattern),
                        func.lower(func.coalesce(LawyerProfile.handle, "")).like(pattern),
                    )
                )
            rows = (
                db_query.order_by(
                    LawyerProfile.verified.desc(),
                    User.role.asc(),
                    User.full_name.asc(),
                )
                .limit(limit)
                .all()
            )
            return MessageUserDirectoryResponse(
                users=[self._serialize_participant(user, profile) for user, profile in rows]
            )
        finally:
            session.close()

    def list_conversations(self, current_user: User) -> ConversationListResponse:
        session = SessionLocal()
        try:
            rows = (
                session.query(DirectConversation)
                .filter(
                    or_(
                        DirectConversation.participant_a_id == current_user.id,
                        DirectConversation.participant_b_id == current_user.id,
                    )
                )
                .order_by(
                    DirectConversation.last_message_at.desc().nullslast(),
                    DirectConversation.updated_at.desc(),
                )
                .all()
            )
            return ConversationListResponse(
                conversations=[self._serialize_conversation_summary(session, row, current_user.id) for row in rows]
            )
        finally:
            session.close()

    def get_conversation(self, conversation_id: int, current_user: User) -> ConversationDetailResponse:
        session = SessionLocal()
        try:
            conversation = self._require_conversation(session, conversation_id, current_user.id)
            now = datetime.utcnow()
            unread_messages = (
                session.query(DirectMessage)
                .filter(
                    DirectMessage.conversation_id == conversation.id,
                    DirectMessage.recipient_user_id == current_user.id,
                    DirectMessage.read_at.is_(None),
                )
                .all()
            )
            for message in unread_messages:
                message.read_at = now
                session.add(message)
            if unread_messages:
                session.commit()

            messages = (
                session.query(DirectMessage)
                .filter(DirectMessage.conversation_id == conversation.id)
                .order_by(DirectMessage.created_at.asc(), DirectMessage.id.asc())
                .limit(200)
                .all()
            )
            return ConversationDetailResponse(
                conversation=self._serialize_conversation_summary(session, conversation, current_user.id),
                messages=[self._serialize_message(session, row, current_user.id) for row in messages],
            )
        finally:
            session.close()

    def start_conversation(self, participant_id: str, current_user: User) -> ConversationDetailResponse:
        session = SessionLocal()
        try:
            participant = self._require_participant(session, participant_id, current_user.id)
            pair = self._participant_pair(current_user.id, participant.id)
            conversation = (
                session.query(DirectConversation)
                .filter(
                    DirectConversation.participant_a_id == pair[0],
                    DirectConversation.participant_b_id == pair[1],
                )
                .first()
            )
            if not conversation:
                now = datetime.utcnow()
                conversation = DirectConversation(
                    participant_a_id=pair[0],
                    participant_b_id=pair[1],
                    created_at=now,
                    updated_at=now,
                )
                session.add(conversation)
                session.commit()
                session.refresh(conversation)
            return ConversationDetailResponse(
                conversation=self._serialize_conversation_summary(session, conversation, current_user.id),
                messages=[],
            )
        finally:
            session.close()

    def start_conversation_with_lawyer(self, handle: str, current_user: User) -> ConversationDetailResponse:
        session = SessionLocal()
        try:
            normalized = handle.strip().lower().lstrip("@")
            profile = (
                session.query(LawyerProfile)
                .filter(func.lower(LawyerProfile.handle) == normalized)
                .first()
            )
            if not profile:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lawyer profile not found.")
            if not profile.user_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This lawyer profile is public, but direct messaging will unlock after the lawyer activates an account.",
                )
            target_user_id = profile.user_id
        finally:
            session.close()
        return self.start_conversation(target_user_id, current_user)

    def send_message(self, conversation_id: int, content: str, current_user: User) -> DirectMessageResponse:
        session = SessionLocal()
        try:
            conversation = self._require_conversation(session, conversation_id, current_user.id)
            recipient_id = (
                conversation.participant_b_id
                if conversation.participant_a_id == current_user.id
                else conversation.participant_a_id
            )
            self._require_participant(session, recipient_id, current_user.id, allow_self=False)
            trimmed = content.strip()
            if not trimmed:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Message content is required.",
                )
            now = datetime.utcnow()
            message = DirectMessage(
                conversation_id=conversation.id,
                sender_user_id=current_user.id,
                recipient_user_id=recipient_id,
                content=trimmed,
                created_at=now,
            )
            conversation.last_message_preview = trimmed[:280]
            conversation.last_message_at = now
            conversation.updated_at = now
            session.add(message)
            session.add(conversation)
            session.commit()
            session.refresh(message)
            return self._serialize_message(session, message, current_user.id)
        finally:
            session.close()

    def _serialize_participant(
        self,
        user: User,
        lawyer_profile: LawyerProfile | None = None,
    ) -> MessageParticipantResponse:
        return MessageParticipantResponse(
            id=user.id,
            full_name=user.full_name,
            role=user.role,
            email=user.email,
            lawyer_handle=lawyer_profile.handle if lawyer_profile else None,
            lawyer_verified=bool(lawyer_profile.verified) if lawyer_profile else False,
        )

    def _serialize_message(
        self,
        session,
        message: DirectMessage,
        current_user_id: str,
    ) -> DirectMessageResponse:
        sender = session.get(User, message.sender_user_id)
        recipient = session.get(User, message.recipient_user_id)
        if not sender or not recipient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message participant not found.")
        sender_profile = session.query(LawyerProfile).filter(LawyerProfile.user_id == sender.id).first()
        recipient_profile = session.query(LawyerProfile).filter(LawyerProfile.user_id == recipient.id).first()
        return DirectMessageResponse(
            id=message.id,
            conversation_id=message.conversation_id,
            sender=self._serialize_participant(sender, sender_profile),
            recipient=self._serialize_participant(recipient, recipient_profile),
            content=message.content,
            created_at=message.created_at.isoformat(),
            read_at=message.read_at.isoformat() if message.read_at else None,
            is_mine=message.sender_user_id == current_user_id,
        )

    def _serialize_conversation_summary(
        self,
        session,
        conversation: DirectConversation,
        current_user_id: str,
    ) -> ConversationSummaryResponse:
        counterpart_id = (
            conversation.participant_b_id
            if conversation.participant_a_id == current_user_id
            else conversation.participant_a_id
        )
        counterpart = session.get(User, counterpart_id)
        if not counterpart:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation participant not found.")
        counterpart_profile = session.query(LawyerProfile).filter(LawyerProfile.user_id == counterpart.id).first()
        unread_count = (
            session.query(func.count(DirectMessage.id))
            .filter(
                DirectMessage.conversation_id == conversation.id,
                DirectMessage.recipient_user_id == current_user_id,
                DirectMessage.read_at.is_(None),
            )
            .scalar()
            or 0
        )
        return ConversationSummaryResponse(
            id=conversation.id,
            counterpart=self._serialize_participant(counterpart, counterpart_profile),
            last_message_preview=conversation.last_message_preview,
            last_message_at=conversation.last_message_at.isoformat() if conversation.last_message_at else None,
            unread_count=int(unread_count),
        )

    def _require_participant(
        self,
        session,
        participant_id: str,
        current_user_id: str,
        allow_self: bool = False,
    ) -> User:
        if not allow_self and participant_id == current_user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Select another user to start a conversation.",
            )
        participant = session.get(User, participant_id)
        if not participant or not participant.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return participant

    def _require_conversation(self, session, conversation_id: int, current_user_id: str) -> DirectConversation:
        conversation = session.get(DirectConversation, conversation_id)
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        if current_user_id not in {conversation.participant_a_id, conversation.participant_b_id}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Conversation access denied.")
        return conversation

    def _participant_pair(self, first: str, second: str) -> tuple[str, str]:
        return tuple(sorted((first, second)))
