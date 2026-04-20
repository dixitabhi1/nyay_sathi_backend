from __future__ import annotations

import json
import logging

from app.db.session import SessionLocal
from app.models.audit import AuditLog
from app.schemas.history import UserHistoryItem, UserHistoryResponse
from sqlalchemy.exc import SQLAlchemyError


ACTION_CATEGORY_MAP = {
    "chat.query": "chat",
    "research.search": "research",
    "analysis.case": "analysis",
    "analysis.strength": "analysis",
    "analysis.draft": "drafting",
    "analysis.fir": "analysis",
    "documents.contract": "documents",
    "documents.evidence": "documents",
    "documents.template_publish": "drafting",
    "documents.template_checkout": "drafting",
    "documents.template_verify_payment": "drafting",
    "fir.manual": "fir",
    "fir.upload": "fir",
    "fir.voice": "fir",
    "fir.update_draft": "fir",
    "fir.evidence": "fir",
}

logger = logging.getLogger(__name__)


class UserHistoryService:
    def list_history(self, user_id: str, category: str | None = None, limit: int = 50) -> UserHistoryResponse:
        session = SessionLocal()
        try:
            query = (
                session.query(AuditLog)
                .filter(AuditLog.user_id == user_id)
                .order_by(AuditLog.created_at.desc())
            )
            rows = query.limit(max(1, min(limit, 200))).all()
            items = [self._to_item(row) for row in rows]
            if category:
                items = [item for item in items if item.category == category]
            return UserHistoryResponse(items=items[:limit])
        except SQLAlchemyError as exc:
            logger.warning("History lookup failed for user %s: %s", user_id, exc)
            return UserHistoryResponse(items=[])
        finally:
            session.close()

    def _to_item(self, row: AuditLog) -> UserHistoryItem:
        input_payload = self._load_json(row.input_payload)
        output_payload = self._load_json(row.output_payload)
        category = ACTION_CATEGORY_MAP.get(row.action, "other")
        title = self._build_title(row.action, input_payload, output_payload)
        prompt_excerpt = self._prompt_excerpt(row.action, input_payload)
        result_excerpt = self._result_excerpt(row.action, output_payload)
        return UserHistoryItem(
            id=row.id,
            action=row.action,
            category=category,
            title=title,
            prompt_excerpt=prompt_excerpt,
            result_excerpt=result_excerpt,
            created_at=row.created_at.isoformat() if row.created_at else "",
        )

    def _load_json(self, raw: str) -> dict:
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _build_title(self, action: str, input_payload: dict, output_payload: dict) -> str:
        if action == "chat.query":
            return input_payload.get("question", "Legal chat")[:80]
        if action == "research.search":
            return input_payload.get("query", "Legal research")[:80]
        if action == "analysis.case":
            return "Case analysis"
        if action == "analysis.strength":
            return "Case strength prediction"
        if action == "analysis.draft":
            return f"Draft: {input_payload.get('draft_type', 'document')}"[:80]
        if action in {"documents.contract", "documents.evidence"}:
            return f"{action.split('.')[1].title()} analysis"
        if action == "documents.template_publish":
            return f"Published: {input_payload.get('title', 'Document template')}"[:80]
        if action == "documents.template_checkout":
            return f"Document order #{output_payload.get('order', {}).get('id', '')}".strip()
        if action == "documents.template_verify_payment":
            return f"Unlocked document order #{input_payload.get('order_id', '')}".strip()
        if action.startswith("fir."):
            fir_id = output_payload.get("fir_id") or input_payload.get("fir_id")
            return f"FIR {action.split('.')[1].replace('_', ' ').title()}" + (f" ({fir_id})" if fir_id else "")
        return action

    def _prompt_excerpt(self, action: str, input_payload: dict) -> str | None:
        for key in ("question", "query", "incident_description", "facts", "transcript_text"):
            value = input_payload.get(key)
            if value:
                return str(value)[:200]
        if action == "documents.template_checkout":
            answers = input_payload.get("answers")
            if answers:
                return json.dumps(answers, ensure_ascii=True)[:200]
        return None

    def _result_excerpt(self, action: str, output_payload: dict) -> str | None:
        for key in ("answer", "summary", "draft_text", "content", "legal_reasoning", "fir_text"):
            value = output_payload.get(key)
            if value:
                return str(value)[:200]
        if action.startswith("documents.template_"):
            order = output_payload.get("order", output_payload)
            generated = order.get("generated_document_text")
            if generated:
                return str(generated)[:200]
        return None
