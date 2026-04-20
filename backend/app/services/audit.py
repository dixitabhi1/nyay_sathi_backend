import json
import logging
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from app.db.session import SessionLocal
from app.models.audit import AuditLog


logger = logging.getLogger(__name__)


class AuditService:
    def log(self, action: str, input_payload: dict, output_payload: dict, user_id: str | None = None) -> None:
        session = SessionLocal()
        try:
            record = AuditLog(
                action=action,
                user_id=user_id,
                input_payload=self._serialize_payload(input_payload),
                output_payload=self._serialize_payload(output_payload),
            )
            session.add(record)
            session.commit()
        except Exception as exc:  # pragma: no cover - audit failures must never break primary flows
            session.rollback()
            logger.warning("Audit logging skipped for %s: %s", action, exc)
        finally:
            session.close()

    def _serialize_payload(self, payload: object) -> str:
        if hasattr(payload, "model_dump"):
            try:
                payload = payload.model_dump(mode="json")  # type: ignore[assignment]
            except TypeError:
                payload = payload.model_dump()  # type: ignore[assignment]
        return json.dumps(payload, ensure_ascii=True, default=self._json_default)

    def _json_default(self, value: object) -> object:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, set):
            return sorted(value)
        return str(value)
