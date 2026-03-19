from fastapi import APIRouter, Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import get_current_admin_user, get_current_user, security
from app.core.dependencies import get_auth_service
from app.models.auth import User
from app.schemas.auth import (
    AuthLoginRequest,
    AuthLogoutResponse,
    AuthRegisterRequest,
    AuthTokenResponse,
    PendingRoleApplicationsResponse,
    RoleApprovalRequest,
    UserResponse,
)
from app.services.auth import AuthService


router = APIRouter()


@router.post("/register", response_model=AuthTokenResponse)
def register(
    payload: AuthRegisterRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    user_agent: str | None = Header(default=None),
) -> AuthTokenResponse:
    return auth_service.register_user(
        email=payload.email,
        full_name=payload.full_name,
        password=payload.password,
        role=payload.role,
        professional_id=payload.professional_id,
        organization=payload.organization,
        city=payload.city,
        preferred_language=payload.preferred_language,
        user_agent=user_agent,
        ip_address=request.client.host if request.client else None,
    )


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: AuthLoginRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    user_agent: str | None = Header(default=None),
) -> AuthTokenResponse:
    return auth_service.login_user(
        email=payload.email,
        password=payload.password,
        user_agent=user_agent,
        ip_address=request.client.host if request.client else None,
    )


@router.get("/me", response_model=UserResponse)
def me(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    return auth_service.serialize_user(current_user)


@router.post("/logout", response_model=AuthLogoutResponse)
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthLogoutResponse:
    if credentials and credentials.scheme.lower() == "bearer":
        auth_service.revoke_token(credentials.credentials)
    return AuthLogoutResponse()


@router.get("/approvals", response_model=PendingRoleApplicationsResponse)
def pending_role_approvals(
    auth_service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(get_current_admin_user),
) -> PendingRoleApplicationsResponse:
    return auth_service.list_pending_role_applications()


@router.post("/approvals/{user_id}", response_model=UserResponse)
def update_role_approval(
    user_id: str,
    payload: RoleApprovalRequest,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(get_current_admin_user),
) -> UserResponse:
    return auth_service.update_role_approval(user_id, payload.approval_status, payload.notes)
