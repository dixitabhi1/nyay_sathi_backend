from __future__ import annotations

from datetime import datetime
import json

from sqlalchemy import func

from app.db.session import SessionLocal
from app.models.auth import User
from app.models.fir import FIRRecord
from app.models.lawyer import LawyerProfile
from app.schemas.admin import (
    AdminDashboardResponse,
    AdminFIRQueueItemResponse,
    AdminLawyerProfileReviewResponse,
    AdminMetricResponse,
)
from app.schemas.auth import PendingRoleApplicationsResponse
from app.schemas.fir import FIRStructuredData
from app.services.auth import APPROVAL_REQUIRED_ROLES, AuthService


class AdminService:
    def __init__(self, auth_service: AuthService) -> None:
        self.auth_service = auth_service

    def get_dashboard(self, limit: int = 12) -> AdminDashboardResponse:
        session = SessionLocal()
        try:
            total_users = session.query(func.count(User.id)).scalar() or 0
            pending_lawyers = self._count_role_status(session, "lawyer", "pending")
            pending_police = self._count_role_status(session, "police", "pending")
            approved_lawyers = self._count_role_status(session, "lawyer", "approved")
            approved_police = self._count_role_status(session, "police", "approved")
            verified_lawyers = session.query(func.count(LawyerProfile.id)).filter(LawyerProfile.verified.is_(True)).scalar() or 0
            total_firs = session.query(func.count(FIRRecord.id)).scalar() or 0

            pending_applications = self.auth_service.list_pending_role_applications().applications[:limit]

            recent_profiles = (
                session.query(LawyerProfile, User.email)
                .outerjoin(User, User.id == LawyerProfile.user_id)
                .order_by(LawyerProfile.created_at.desc())
                .limit(limit)
                .all()
            )
            recent_firs = (
                session.query(FIRRecord)
                .order_by(FIRRecord.last_edited_at.desc())
                .limit(limit)
                .all()
            )

            return AdminDashboardResponse(
                metrics=[
                    AdminMetricResponse(
                        title="Platform accounts",
                        value=str(total_users),
                        detail="Total registered NyayaSetu users across all roles.",
                    ),
                    AdminMetricResponse(
                        title="Pending professionals",
                        value=str(pending_lawyers + pending_police),
                        detail=f"{pending_lawyers} lawyer and {pending_police} police approvals are waiting.",
                    ),
                    AdminMetricResponse(
                        title="Approved professionals",
                        value=str(approved_lawyers + approved_police),
                        detail=f"{approved_lawyers} lawyer and {approved_police} police accounts are approved.",
                    ),
                    AdminMetricResponse(
                        title="Verified lawyer profiles",
                        value=str(verified_lawyers),
                        detail="Public lawyer profiles marked verified in the marketplace.",
                    ),
                    AdminMetricResponse(
                        title="FIR drafts",
                        value=str(total_firs),
                        detail="Saved FIR records available for police, citizen, and lawyer workflows.",
                    ),
                ],
                pending_applications=pending_applications,
                recent_lawyer_profiles=[
                    AdminLawyerProfileReviewResponse(
                        handle=profile.handle,
                        name=profile.name,
                        verification_status=profile.verification_status,
                        specialization=profile.specialization,
                        city=profile.city,
                        bar_council_id=profile.bar_council_id,
                        linked_user_email=email,
                        created_at=profile.created_at,
                    )
                    for profile, email in recent_profiles
                ],
                recent_firs=[self._serialize_fir(record) for record in recent_firs],
                generated_at=datetime.utcnow(),
            )
        finally:
            session.close()

    def _count_role_status(self, session, role: str, status: str) -> int:
        if role not in APPROVAL_REQUIRED_ROLES:
            return 0
        return (
            session.query(func.count(User.id))
            .filter(User.requested_role == role, User.approval_status == status)
            .scalar()
            or 0
        )

    def _serialize_fir(self, record: FIRRecord) -> AdminFIRQueueItemResponse:
        extracted_raw = json.loads(record.extracted_payload)
        extracted = FIRStructuredData.model_validate(extracted_raw)
        return AdminFIRQueueItemResponse(
            fir_id=record.id,
            workflow=record.workflow,
            draft_role=record.draft_role,
            status=record.status,
            complainant_name=extracted.complainant_name,
            police_station=extracted.police_station,
            incident_date=extracted.incident_date,
            incident_location=extracted.incident_location,
            last_edited_at=record.last_edited_at,
        )
