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
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        requested_role=current_user.requested_role,
        approval_status=current_user.approval_status,
        professional_id=current_user.professional_id,
        organization=current_user.organization,
        city=current_user.city,
        preferred_language=current_user.preferred_language,
        approval_notes=current_user.approval_notes,
        can_access_lawyer_dashboard=current_user.role == "lawyer" and current_user.approval_status == "approved",
        can_access_police_dashboard=current_user.role == "police" and current_user.approval_status == "approved",
        can_access_admin_dashboard=current_user.role == "admin" and current_user.approval_status == "approved",
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
    )


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
