from datetime import datetime

from pydantic import BaseModel, Field


class AuthRegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="citizen", min_length=3, max_length=64)
    professional_id: str | None = Field(default=None, max_length=128)
    organization: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=128)
    preferred_language: str = Field(default="en", min_length=2, max_length=32)


class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    requested_role: str
    approval_status: str
    professional_id: str | None = None
    organization: str | None = None
    city: str | None = None
    preferred_language: str
    approval_notes: str | None = None
    can_access_lawyer_dashboard: bool = False
    can_access_police_dashboard: bool = False
    can_access_admin_dashboard: bool = False
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserResponse


class AuthLogoutResponse(BaseModel):
    success: bool = True
    detail: str = "Logged out successfully."


class RoleApprovalRequest(BaseModel):
    approval_status: str = Field(min_length=4, max_length=32)
    notes: str | None = Field(default=None, max_length=1000)


class PendingRoleApplicationLinkedProfileResponse(BaseModel):
    handle: str
    verification_status: str
    specialization: str
    bar_council_id: str
    city: str


class PendingRoleApplicationResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    requested_role: str
    approval_status: str
    professional_id: str | None = None
    organization: str | None = None
    city: str | None = None
    preferred_language: str
    approval_notes: str | None = None
    last_login_at: datetime | None = None
    linked_profile: PendingRoleApplicationLinkedProfileResponse | None = None
    created_at: datetime


class PendingRoleApplicationsResponse(BaseModel):
    applications: list[PendingRoleApplicationResponse]
