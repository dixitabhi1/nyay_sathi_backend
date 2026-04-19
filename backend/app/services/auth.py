from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import hmac
import logging
import secrets
import uuid

from fastapi import HTTPException, status

from app.core.config import Settings
from app.db.session import SessionLocal, engine
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
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AuthenticatedSession:
    user: User
    session: AuthSession


def get_missing_user_login_detail(
    *,
    is_huggingface_space: bool,
    resolved_database_url: str,
    engine_drivername: str,
    space_local_app_db_fallback_reason: str | None,
) -> str:
    if not resolved_database_url.startswith("sqlite+libsql://") or engine_drivername == "sqlite+libsql":
        return "Invalid email or password."

    if is_huggingface_space and space_local_app_db_fallback_reason:
        return (
            "This deployment is currently using its local auth database instead of the configured remote database. "
            "If your account was created on another deployment, register again or migrate users into the active DB."
        )

    return (
        "The configured auth database is currently unavailable, and this deployment is using a fallback local database. "
        "Existing accounts on the primary database may be temporarily unavailable."
    )


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

    def ensure_allowlisted_admin_accounts(self) -> None:
        allowlisted_emails = sorted(self.settings.admin_email_allowlist)
        if not allowlisted_emails:
            return

        session = SessionLocal()
        try:
            for email in allowlisted_emails:
                user = session.query(User).filter(User.email == email).first()
                if user is None:
                    if not self.settings.bootstrap_admin_password:
                        logger.warning(
                            "Allowlisted admin email %s is missing and BOOTSTRAP_ADMIN_PASSWORD is not configured.",
                            email,
                        )
                        continue
                    session.add(
                        User(
                            id=uuid.uuid4().hex,
                            email=email,
                            full_name=self.settings.bootstrap_admin_full_name.strip() or "NyayaSetu Admin",
                            role="admin",
                            requested_role="admin",
                            approval_status="approved",
                            preferred_language="en",
                            approval_notes="Bootstrap admin account restored automatically on startup.",
                            approval_updated_at=datetime.utcnow(),
                            password_hash=self._hash_password(self.settings.bootstrap_admin_password),
                            is_active=True,
                        )
                    )
                    logger.info("Bootstrapped missing admin account for %s.", email)
                    continue

                changed = False
                if user.role != "admin":
                    user.role = "admin"
                    changed = True
                if user.requested_role != "admin":
                    user.requested_role = "admin"
                    changed = True
                if user.approval_status != "approved":
                    user.approval_status = "approved"
                    changed = True
                if not user.is_active:
                    user.is_active = True
                    changed = True
                if self.settings.bootstrap_admin_password and self._password_hash_needs_rehash(user.password_hash):
                    user.password_hash = self._hash_password(self.settings.bootstrap_admin_password)
                    changed = True
                if changed:
                    user.approval_notes = "Admin account synchronized automatically from the operator allowlist."
                    user.approval_updated_at = datetime.utcnow()
                    user.updated_at = datetime.utcnow()
                    session.add(user)

            session.commit()
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
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=get_missing_user_login_detail(
                        is_huggingface_space=self.settings.is_huggingface_space,
                        resolved_database_url=self.settings.resolved_database_url,
                        engine_drivername=engine.url.drivername,
                        space_local_app_db_fallback_reason=self.settings.space_local_app_db_fallback_reason,
                    ),
                )
            if not self._verify_password(password, user.password_hash):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
            if not user.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is inactive.")
            if self._password_hash_needs_rehash(user.password_hash):
                user.password_hash = self._hash_password(password)
                user.updated_at = datetime.utcnow()
                session.add(user)
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
        iterations = self.settings.resolved_auth_password_hash_iterations
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

    def _password_hash_needs_rehash(self, stored_hash: str) -> bool:
        try:
            algorithm, iteration_text, *_ = stored_hash.split("$", 3)
        except ValueError:
            return True
        if algorithm != "pbkdf2_sha256":
            return True
        try:
            stored_iterations = int(iteration_text)
        except ValueError:
            return True
        return stored_iterations != self.settings.resolved_auth_password_hash_iterations

    def _hash_token(self, token: str) -> str:
        secret = self.settings.auth_secret_key.encode("utf-8")
        return hmac.new(secret, token.encode("utf-8"), hashlib.sha256).hexdigest()

    def _is_admin_email(self, email: str) -> bool:
        return email.strip().lower() in self.settings.admin_email_allowlist
