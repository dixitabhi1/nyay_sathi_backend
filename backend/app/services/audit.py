import json

from app.db.session import SessionLocal
from app.models.audit import AuditLog


class AuditService:
    def log(self, action: str, input_payload: dict, output_payload: dict, user_id: str | None = None) -> None:
        session = SessionLocal()
        try:
            record = AuditLog(
                action=action,
                user_id=user_id,
                input_payload=json.dumps(input_payload, ensure_ascii=True),
                output_payload=json.dumps(output_payload, ensure_ascii=True),
            )
            session.add(record)
            session.commit()
        finally:
            session.close()

