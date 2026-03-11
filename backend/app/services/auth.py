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
from app.schemas.auth import AuthTokenResponse, UserResponse


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
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthTokenResponse:
        normalized_email = self._normalize_email(email)
        session = SessionLocal()
        try:
            existing = session.query(User).filter(User.email == normalized_email).first()
            if existing:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

            user = User(
                id=uuid.uuid4().hex,
                email=normalized_email,
                full_name=full_name.strip(),
                role=role.strip().lower(),
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
        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )

    def _normalize_email(self, email: str) -> str:
        normalized = email.strip().lower()
        if "@" not in normalized or "." not in normalized.split("@")[-1]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter a valid email address.")
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
