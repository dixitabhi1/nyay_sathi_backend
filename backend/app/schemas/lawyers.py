from datetime import datetime

from pydantic import BaseModel, Field


class LawyerSocialUserResponse(BaseModel):
    name: str
    role: str


class LawyerFollowerResponse(LawyerSocialUserResponse):
    followed_at: str


class LawyerPostLikeResponse(LawyerSocialUserResponse):
    liked_at: str


class LawyerReviewResponse(BaseModel):
    author: str
    text: str
    rating: int
    created_at: str


class LawyerArticleResponse(BaseModel):
    category: str
    title: str
    excerpt: str
    created_at: str


class LawyerProfileSummaryResponse(BaseModel):
    handle: str
    name: str
    bar_council_id: str
    years_of_practice: int
    experience: str
    specialization: str
    courts: str
    city: str
    languages: list[str]
    fee: str
    rating: float
    review_count: int
    bio: str
    verified: bool
    verification_status: str
    follower_count: int = 0
    article_count: int = 0
    public_url: str


class LawyerProfileDetailResponse(LawyerProfileSummaryResponse):
    about: str
    case_experience: list[str]
    reviews: list[LawyerReviewResponse]
    articles: list[LawyerArticleResponse]
    followers: list[LawyerFollowerResponse]
    is_following: bool = False
    messaging_enabled: bool = False
    created_at: str
    updated_at: str


class LawyerDirectoryResponse(BaseModel):
    lawyers: list[LawyerProfileSummaryResponse]
    total_lawyers: int
    average_rating: float
    verified_percentage: int


class LawyerNetworkPostResponse(BaseModel):
    id: int
    handle: str
    author: str
    category: str
    title: str
    excerpt: str
    like_count: int
    comment_count: int
    stats: str
    liked_by: list[LawyerPostLikeResponse]
    is_liked: bool = False
    public_url: str
    created_at: str


class LawyerNetworkFeedResponse(BaseModel):
    posts: list[LawyerNetworkPostResponse]


class LawyerRegistrationRequest(BaseModel):
    handle: str = Field(min_length=3, max_length=64)
    name: str = Field(min_length=2, max_length=255)
    bar_council_id: str = Field(min_length=3, max_length=128)
    years_of_practice: int = Field(ge=0, le=70)
    specialization: str = Field(min_length=2, max_length=255)
    courts_practiced_in: str = Field(min_length=2, max_length=1000)
    city: str = Field(min_length=2, max_length=128)
    languages: list[str] = Field(default_factory=list)
    consultation_fee: str = Field(min_length=1, max_length=128)
    profile_photo_url: str | None = Field(default=None, max_length=512)
    bio: str = Field(min_length=20, max_length=4000)
    about: str | None = Field(default=None, max_length=4000)
    case_experience: list[str] = Field(default_factory=list)


class LawyerRegistrationResponse(BaseModel):
    message: str = "Profile submitted for verification."
    profile: LawyerProfileDetailResponse


class LawyerFollowersResponse(BaseModel):
    handle: str
    follower_count: int
    followers: list[LawyerFollowerResponse]


class LawyerFollowToggleResponse(BaseModel):
    handle: str
    following: bool
    follower_count: int
    followers: list[LawyerFollowerResponse]


class LawyerPostLikeToggleResponse(BaseModel):
    post_id: int
    liked: bool
    like_count: int
    liked_by: list[LawyerPostLikeResponse]


class LawyerNetworkPostCreateRequest(BaseModel):
    category: str = Field(min_length=2, max_length=128)
    title: str = Field(min_length=6, max_length=255)
    excerpt: str = Field(min_length=20, max_length=1200)
    content: str | None = Field(default=None, max_length=5000)


class PoliceDashboardCardResponse(BaseModel):
    title: str
    value: str
    detail: str


class PoliceQueueItemResponse(BaseModel):
    fir_id: str
    title: str
    status: str
    detail: str
    workflow: str
    police_station: str | None = None
    last_edited_at: str


class PoliceHotspotAlertResponse(BaseModel):
    title: str
    detail: str


class PoliceDashboardResponse(BaseModel):
    cards: list[PoliceDashboardCardResponse]
    queue: list[PoliceQueueItemResponse]
    hotspot_alerts: list[PoliceHotspotAlertResponse]
    generated_at: datetime


class LawyerDashboardMetricResponse(BaseModel):
    title: str
    value: str
    detail: str


class LawyerDashboardConversationResponse(BaseModel):
    conversation_id: int
    counterpart_name: str
    counterpart_role: str
    preview: str
    unread_count: int
    last_message_at: str | None = None


class LawyerDashboardResponse(BaseModel):
    metrics: list[LawyerDashboardMetricResponse]
    recent_followers: list[LawyerFollowerResponse]
    top_posts: list[LawyerNetworkPostResponse]
    recent_conversations: list[LawyerDashboardConversationResponse]
    generated_at: datetime
