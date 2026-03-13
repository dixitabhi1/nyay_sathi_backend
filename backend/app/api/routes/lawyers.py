from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_lawyer_network_service
from app.core.security import get_optional_current_user
from app.models.auth import User
from app.schemas.lawyers import (
    LawyerDirectoryResponse,
    LawyerNetworkFeedResponse,
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
) -> LawyerNetworkFeedResponse:
    return lawyer_service.list_network_feed(limit=limit)


@router.get("/police/dashboard", response_model=PoliceDashboardResponse)
def police_dashboard(
    limit: int = Query(default=8, ge=1, le=50),
    lawyer_service: LawyerNetworkService = Depends(get_lawyer_network_service),
) -> PoliceDashboardResponse:
    return lawyer_service.get_police_dashboard(limit=limit)


@router.get("/{handle}", response_model=LawyerProfileDetailResponse)
def lawyer_profile(
    handle: str,
    lawyer_service: LawyerNetworkService = Depends(get_lawyer_network_service),
) -> LawyerProfileDetailResponse:
    return lawyer_service.get_profile(handle)
