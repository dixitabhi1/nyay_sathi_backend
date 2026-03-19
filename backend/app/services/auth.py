from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import hmac
import secrets
import uuid

from fastapi import HTTPException, status

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.auth import AuthSession, User
from app.models.lawyer import LawyerProfile
from app.schemas.auth import (
    AuthTokenResponse,
    PendingRoleApplicationLinkedProfileResponse,
    PendingRoleApplicationResponse,
    PendingRoleApplicationsResponse,
    UserResponse,
)


APPROVAL_REQUIRED_ROLES = {"lawyer", "police"}
DIRECT_ACCESS_ROLES = {"citizen", "admin"}


@dataclass(slots=True)
class AuthenticatedSession:
    user: User
    session: AuthSession


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def register_user(
        self,
        email: str,
        full_name: str,
        password: str,
        role: str = "citizen",
        professional_id: str | None = None,
        organization: str | None = None,
        city: str | None = None,
        preferred_language: str = "en",
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthTokenResponse:
        normalized_email = self._normalize_email(email)
        requested_role = self._normalize_role(role)
        if requested_role == "admin" and not self._is_admin_email(normalized_email):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin registration is restricted to configured operator emails.",
            )
        session = SessionLocal()
        try:
            existing = session.query(User).filter(User.email == normalized_email).first()
            if existing:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

            approval_status = "approved" if requested_role in DIRECT_ACCESS_ROLES else "pending"
            granted_role = requested_role if approval_status == "approved" else "citizen"
            approval_notes = (
                None
                if approval_status == "approved"
                else f"{requested_role.title()} access is pending verification and approval."
            )

            user = User(
                id=uuid.uuid4().hex,
                email=normalized_email,
                full_name=full_name.strip(),
                role=granted_role,
                requested_role=requested_role,
                approval_status=approval_status,
                professional_id=(professional_id.strip() if professional_id else None),
                organization=(organization.strip() if organization else None),
                city=(city.strip() if city else None),
                preferred_language=preferred_language.strip().lower() or "en",
                approval_notes=approval_notes,
                approval_updated_at=datetime.utcnow(),
                password_hash=self._hash_password(password),
                is_active=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return self._issue_session(session, user, user_agent, ip_address)
        finally:
            session.close()

    def login_user(
        self,
        email: str,
        password: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthTokenResponse:
        normalized_email = self._normalize_email(email)
        session = SessionLocal()
        try:
            user = session.query(User).filter(User.email == normalized_email).first()
            if not user or not self._verify_password(password, user.password_hash):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
            if not user.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is inactive.")
            return self._issue_session(session, user, user_agent, ip_address)
        finally:
            session.close()

    def list_pending_role_applications(self) -> PendingRoleApplicationsResponse:
        session = SessionLocal()
        try:
            rows = (
                session.query(User)
                .filter(User.requested_role.in_(APPROVAL_REQUIRED_ROLES))
                .filter(User.approval_status.in_(["pending", "rejected"]))
                .order_by(User.created_at.desc())
                .all()
            )
            profiles = {
                profile.user_id: profile
                for profile in session.query(LawyerProfile)
                .filter(LawyerProfile.user_id.is_not(None))
                .all()
                if profile.user_id
            }
            return PendingRoleApplicationsResponse(
                applications=[
                    PendingRoleApplicationResponse(
                        id=row.id,
                        email=row.email,
                        full_name=row.full_name,
                        role=row.role,
                        requested_role=row.requested_role,
                        approval_status=row.approval_status,
                        professional_id=row.professional_id,
                        organization=row.organization,
                        city=row.city,
                        preferred_language=row.preferred_language,
                        approval_notes=row.approval_notes,
                        last_login_at=row.last_login_at,
                        linked_profile=self._serialize_linked_profile(profiles.get(row.id)),
                        created_at=row.created_at,
                    )
                    for row in rows
                ]
            )
        finally:
            session.close()

    def update_role_approval(
        self,
        user_id: str,
        approval_status: str,
        notes: str | None = None,
    ) -> UserResponse:
        normalized_status = approval_status.strip().lower()
        if normalized_status not in {"approved", "rejected", "pending"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Approval status must be approved, rejected, or pending.",
            )
        session = SessionLocal()
        try:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
            user.approval_status = normalized_status
            user.approval_notes = notes.strip() if notes else None
            user.approval_updated_at = datetime.utcnow()
            if normalized_status == "approved":
                user.role = user.requested_role
            elif user.requested_role in APPROVAL_REQUIRED_ROLES:
                user.role = "citizen"
            user.updated_at = datetime.utcnow()
            session.add(user)
            session.commit()
            session.refresh(user)
            return self._serialize_user(user)
        finally:
            session.close()

    def get_user_from_token(self, token: str) -> User:
        token_hash = self._hash_token(token)
        session = SessionLocal()
        try:
            auth_session = (
                session.query(AuthSession)
                .filter(AuthSession.token_hash == token_hash, AuthSession.revoked_at.is_(None))
                .first()
            )
            if not auth_session:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token.")
            if auth_session.expires_at <= datetime.utcnow():
                auth_session.revoked_at = datetime.utcnow()
                session.add(auth_session)
                session.commit()
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token has expired.")

            user = session.get(User, auth_session.user_id)
            if not user or not user.is_active:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is unavailable.")
            return user
        finally:
            session.close()

    def revoke_token(self, token: str) -> None:
        token_hash = self._hash_token(token)
        session = SessionLocal()
        try:
            auth_session = (
                session.query(AuthSession)
                .filter(AuthSession.token_hash == token_hash, AuthSession.revoked_at.is_(None))
                .first()
            )
            if auth_session:
                auth_session.revoked_at = datetime.utcnow()
                session.add(auth_session)
                session.commit()
        finally:
            session.close()

    def serialize_user(self, user: User) -> UserResponse:
        return self._serialize_user(user)

    def _issue_session(
        self,
        session,
        user: User,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthTokenResponse:
        raw_token = secrets.token_urlsafe(48)
        expires_at = datetime.utcnow() + timedelta(hours=self.settings.auth_token_ttl_hours)
        auth_session = AuthSession(
            user_id=user.id,
            token_hash=self._hash_token(raw_token),
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=expires_at,
        )
        user.last_login_at = datetime.utcnow()
        user.updated_at = datetime.utcnow()
        session.add(auth_session)
        session.add(user)
        session.commit()
        session.refresh(user)
        return AuthTokenResponse(
            access_token=raw_token,
            expires_at=expires_at,
            user=self._serialize_user(user),
        )

    def _serialize_user(self, user: User) -> UserResponse:
        can_access_lawyer_dashboard = user.role == "lawyer" and user.approval_status == "approved"
        can_access_police_dashboard = user.role == "police" and user.approval_status == "approved"
        can_access_admin_dashboard = self._is_admin_email(user.email) or (
            user.role == "admin" and user.approval_status == "approved"
        )
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            requested_role=user.requested_role,
            approval_status=user.approval_status,
            professional_id=user.professional_id,
            organization=user.organization,
            city=user.city,
            preferred_language=user.preferred_language,
            approval_notes=user.approval_notes,
            can_access_lawyer_dashboard=can_access_lawyer_dashboard,
            can_access_police_dashboard=can_access_police_dashboard,
            can_access_admin_dashboard=can_access_admin_dashboard,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )

    def _serialize_linked_profile(
        self,
        profile: LawyerProfile | None,
    ) -> PendingRoleApplicationLinkedProfileResponse | None:
        if profile is None:
            return None
        return PendingRoleApplicationLinkedProfileResponse(
            handle=profile.handle,
            verification_status=profile.verification_status,
            specialization=profile.specialization,
            bar_council_id=profile.bar_council_id,
            city=profile.city,
        )

    def _normalize_email(self, email: str) -> str:
        normalized = email.strip().lower()
        if "@" not in normalized or "." not in normalized.split("@")[-1]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter a valid email address.")
        return normalized

    def _normalize_role(self, role: str) -> str:
        normalized = role.strip().lower() if role else "citizen"
        if normalized not in {"citizen", "lawyer", "police", "admin"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Role must be citizen, lawyer, police, or admin.",
            )
        return normalized

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        iterations = 390000
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
        return f"pbkdf2_sha256${iterations}${salt}${digest}"

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        try:
            algorithm, iteration_text, salt, expected_digest = stored_hash.split("$", 3)
        except ValueError:
            return False
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iteration_text),
        ).hex()
        return hmac.compare_digest(digest, expected_digest)

    def _hash_token(self, token: str) -> str:
        secret = self.settings.auth_secret_key.encode("utf-8")
        return hmac.new(secret, token.encode("utf-8"), hashlib.sha256).hexdigest()

    def _is_admin_email(self, email: str) -> bool:
        return email.strip().lower() in self.settings.admin_email_allowlist
