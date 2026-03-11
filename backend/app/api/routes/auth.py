from fastapi import APIRouter, Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.dependencies import get_auth_service
from app.models.auth import User
from app.schemas.auth import (
    AuthLoginRequest,
    AuthLogoutResponse,
    AuthRegisterRequest,
    AuthTokenResponse,
    UserResponse,
)
from app.services.auth import AuthService


router = APIRouter()
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    if not credentials or credentials.scheme.lower() != "bearer":
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication credentials were not provided.")
    return auth_service.get_user_from_token(credentials.credentials)


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
