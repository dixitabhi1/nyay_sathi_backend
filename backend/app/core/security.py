from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.dependencies import get_auth_service
from app.models.auth import User
from app.services.auth import AuthService


security = HTTPBearer(auto_error=False)


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> User | None:
    if not credentials or credentials.scheme.lower() != "bearer":
        return None
    return auth_service.get_user_from_token(credentials.credentials)


def get_current_user(
    current_user: User | None = Depends(get_optional_current_user),
) -> User:
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
        )
    return current_user


def require_approved_role(required_role: str):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != required_role or current_user.approval_status != "approved":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature is available only to approved {required_role} accounts.",
            )
        return current_user

    return dependency


def get_current_lawyer_user(current_user: User = Depends(require_approved_role("lawyer"))) -> User:
    return current_user


def get_current_police_user(current_user: User = Depends(require_approved_role("police"))) -> User:
    return current_user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin" or current_user.approval_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires an approved admin account.",
        )
    return current_user
