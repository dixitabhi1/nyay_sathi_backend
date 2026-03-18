from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_lawyer_network_service
from app.core.security import get_current_lawyer_user, get_current_police_user, get_current_user, get_optional_current_user
from app.models.auth import User
from app.schemas.lawyers import (
    LawyerDashboardResponse,
    LawyerDirectoryResponse,
    LawyerFollowersResponse,
    LawyerFollowToggleResponse,
    LawyerNetworkFeedResponse,
    LawyerNetworkPostCreateRequest,
    LawyerNetworkPostResponse,
    LawyerPostLikeToggleResponse,
    LawyerProfileDetailResponse,
    LawyerRegistrationRequest,
    LawyerRegistrationResponse,
    PoliceDashboardResponse,
)
from app.services.lawyers import LawyerNetworkService


router = APIRouter()


@router.get("", response_model=LawyerDirectoryResponse)
def list_lawyers(
    query: str | None = None,
    city: str | None = None,
    specialization: str | None = None,
    min_years: int | None = Query(default=None, ge=0),
    verified_only: bool = False,
    limit: int = Query(default=24, ge=1, le=100),
    lawyer_service: LawyerNetworkService = Depends(get_lawyer_network_service),
) -> LawyerDirectoryResponse:
    return lawyer_service.list_lawyers(
        query=query,
        city=city,
        specialization=specialization,
        min_years=min_years,
        verified_only=verified_only,
        limit=limit,
    )


@router.post("/register", response_model=LawyerRegistrationResponse, status_code=status.HTTP_201_CREATED)
def register_lawyer(
    payload: LawyerRegistrationRequest,
    lawyer_service: LawyerNetworkService = Depends(get_lawyer_network_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> LawyerRegistrationResponse:
    return lawyer_service.register_profile(payload, current_user=current_user)


@router.get("/network/feed", response_model=LawyerNetworkFeedResponse)
def lawyer_network_feed(
    limit: int = Query(default=20, ge=1, le=100),
    lawyer_service: LawyerNetworkService = Depends(get_lawyer_network_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> LawyerNetworkFeedResponse:
    return lawyer_service.list_network_feed(limit=limit, current_user=current_user)


@router.post("/network/posts", response_model=LawyerNetworkPostResponse, status_code=status.HTTP_201_CREATED)
def create_network_post(
    payload: LawyerNetworkPostCreateRequest,
    lawyer_service: LawyerNetworkService = Depends(get_lawyer_network_service),
    current_user: User = Depends(get_current_lawyer_user),
) -> LawyerNetworkPostResponse:
    return lawyer_service.create_network_post(payload, current_user=current_user)


@router.post("/network/posts/{post_id}/like", response_model=LawyerPostLikeToggleResponse)
def toggle_post_like(
    post_id: int,
    lawyer_service: LawyerNetworkService = Depends(get_lawyer_network_service),
    current_user: User = Depends(get_current_user),
) -> LawyerPostLikeToggleResponse:
    return lawyer_service.toggle_post_like(post_id, current_user=current_user)


@router.get("/police/dashboard", response_model=PoliceDashboardResponse)
def police_dashboard(
    limit: int = Query(default=8, ge=1, le=50),
    lawyer_service: LawyerNetworkService = Depends(get_lawyer_network_service),
    current_user: User = Depends(get_current_police_user),
) -> PoliceDashboardResponse:
    return lawyer_service.get_police_dashboard(limit=limit)


@router.get("/dashboard/me", response_model=LawyerDashboardResponse)
def lawyer_dashboard(
    lawyer_service: LawyerNetworkService = Depends(get_lawyer_network_service),
    current_user: User = Depends(get_current_lawyer_user),
) -> LawyerDashboardResponse:
    return lawyer_service.get_lawyer_dashboard(current_user=current_user)


@router.get("/{handle}/followers", response_model=LawyerFollowersResponse)
def lawyer_followers(
    handle: str,
    limit: int = Query(default=50, ge=1, le=100),
    lawyer_service: LawyerNetworkService = Depends(get_lawyer_network_service),
) -> LawyerFollowersResponse:
    return lawyer_service.get_followers(handle, limit=limit)


@router.post("/{handle}/follow", response_model=LawyerFollowToggleResponse)
def toggle_follow(
    handle: str,
    lawyer_service: LawyerNetworkService = Depends(get_lawyer_network_service),
    current_user: User = Depends(get_current_user),
) -> LawyerFollowToggleResponse:
    return lawyer_service.toggle_follow(handle, current_user=current_user)


@router.get("/{handle}", response_model=LawyerProfileDetailResponse)
def lawyer_profile(
    handle: str,
    lawyer_service: LawyerNetworkService = Depends(get_lawyer_network_service),
    current_user: User | None = Depends(get_optional_current_user),
) -> LawyerProfileDetailResponse:
    return lawyer_service.get_profile(handle, current_user=current_user)
