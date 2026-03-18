from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, or_

from app.db.session import SessionLocal
from app.models.auth import User
from app.models.lawyer import LawyerFollow, LawyerPost, LawyerPostLike, LawyerProfile, LawyerReview
from app.models.messaging import DirectConversation, DirectMessage
from app.schemas.fir import FIRRecordSummary
from app.schemas.lawyers import (
    LawyerArticleResponse,
    LawyerDashboardConversationResponse,
    LawyerDashboardMetricResponse,
    LawyerDashboardResponse,
    LawyerDirectoryResponse,
    LawyerFollowerResponse,
    LawyerFollowersResponse,
    LawyerFollowToggleResponse,
    LawyerNetworkFeedResponse,
    LawyerNetworkPostCreateRequest,
    LawyerNetworkPostResponse,
    LawyerPostLikeResponse,
    LawyerPostLikeToggleResponse,
    LawyerProfileDetailResponse,
    LawyerProfileSummaryResponse,
    LawyerRegistrationRequest,
    LawyerRegistrationResponse,
    LawyerReviewResponse,
    PoliceDashboardCardResponse,
    PoliceDashboardResponse,
    PoliceHotspotAlertResponse,
    PoliceQueueItemResponse,
)
from app.services.fir_service import FIRService


class LawyerNetworkService:
    def __init__(self, fir_service: FIRService) -> None:
        self.fir_service = fir_service
        self._seed_checked = False

    def list_lawyers(
        self,
        query: str | None = None,
        city: str | None = None,
        specialization: str | None = None,
        min_years: int | None = None,
        verified_only: bool = False,
        limit: int = 24,
    ) -> LawyerDirectoryResponse:
        session = SessionLocal()
        try:
            self._ensure_seed_data(session)
            db_query = session.query(LawyerProfile)
            if verified_only:
                db_query = db_query.filter(LawyerProfile.verified.is_(True))
            if city:
                db_query = db_query.filter(func.lower(LawyerProfile.city) == city.strip().lower())
            if specialization:
                specialization_pattern = f"%{specialization.strip().lower()}%"
                db_query = db_query.filter(func.lower(LawyerProfile.specialization).like(specialization_pattern))
            if min_years is not None:
                db_query = db_query.filter(LawyerProfile.years_of_practice >= min_years)
            if query:
                pattern = f"%{query.strip().lower()}%"
                db_query = db_query.filter(
                    or_(
                        func.lower(LawyerProfile.name).like(pattern),
                        func.lower(LawyerProfile.handle).like(pattern),
                        func.lower(LawyerProfile.specialization).like(pattern),
                        func.lower(LawyerProfile.city).like(pattern),
                        func.lower(LawyerProfile.courts_practiced_in).like(pattern),
                        func.lower(LawyerProfile.languages_json).like(pattern),
                    )
                )

            rows = (
                db_query.order_by(
                    LawyerProfile.verified.desc(),
                    LawyerProfile.rating_average.desc(),
                    LawyerProfile.years_of_practice.desc(),
                    LawyerProfile.name.asc(),
                )
                .limit(limit)
                .all()
            )
            follower_counts = self._follower_counts(session, [row.id for row in rows])
            article_counts = self._article_counts(session, [row.id for row in rows])
            lawyers = [
                self._serialize_profile_summary(
                    row,
                    follower_count=follower_counts.get(row.id, 0),
                    article_count=article_counts.get(row.id, 0),
                )
                for row in rows
            ]
            average_rating = round(sum(item.rating for item in lawyers) / len(lawyers), 1) if lawyers else 0.0
            verified_percentage = round((sum(1 for item in lawyers if item.verified) / len(lawyers)) * 100) if lawyers else 0
            return LawyerDirectoryResponse(
                lawyers=lawyers,
                total_lawyers=len(lawyers),
                average_rating=average_rating,
                verified_percentage=verified_percentage,
            )
        finally:
            session.close()

    def get_profile(
        self,
        handle: str,
        current_user: User | None = None,
    ) -> LawyerProfileDetailResponse:
        session = SessionLocal()
        try:
            self._ensure_seed_data(session)
            normalized_handle = self._normalize_handle(handle)
            profile = (
                session.query(LawyerProfile)
                .filter(func.lower(LawyerProfile.handle) == normalized_handle.lower())
                .first()
            )
            if not profile:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lawyer profile not found.")
            reviews = (
                session.query(LawyerReview)
                .filter(LawyerReview.lawyer_profile_id == profile.id)
                .order_by(LawyerReview.created_at.desc())
                .all()
            )
            articles = (
                session.query(LawyerPost)
                .filter(LawyerPost.lawyer_profile_id == profile.id, LawyerPost.post_kind == "article")
                .order_by(LawyerPost.created_at.desc())
                .all()
            )
            followers = self._load_followers(session, profile.id, limit=25)
            return self._serialize_profile_detail(
                profile,
                reviews,
                articles,
                followers=followers,
                follower_count=self._follower_count(session, profile.id),
                article_count=self._article_count(session, profile.id),
                is_following=self._is_following(session, profile.id, current_user.id) if current_user else False,
            )
        finally:
            session.close()

    def list_network_feed(
        self,
        limit: int = 20,
        current_user: User | None = None,
    ) -> LawyerNetworkFeedResponse:
        session = SessionLocal()
        try:
            self._ensure_seed_data(session)
            rows = (
                session.query(LawyerPost, LawyerProfile)
                .join(LawyerProfile, LawyerProfile.id == LawyerPost.lawyer_profile_id)
                .filter(LawyerPost.post_kind == "feed")
                .order_by(LawyerPost.created_at.desc())
                .limit(limit)
                .all()
            )
            post_ids = [post.id for post, _ in rows]
            liked_ids = self._liked_post_ids(session, post_ids, current_user.id) if current_user else set()
            return LawyerNetworkFeedResponse(
                posts=[
                    self._serialize_post(session, post, profile, is_liked=post.id in liked_ids)
                    for post, profile in rows
                ]
            )
        finally:
            session.close()

    def get_followers(self, handle: str, limit: int = 50) -> LawyerFollowersResponse:
        session = SessionLocal()
        try:
            self._ensure_seed_data(session)
            normalized_handle = self._normalize_handle(handle)
            profile = (
                session.query(LawyerProfile)
                .filter(func.lower(LawyerProfile.handle) == normalized_handle.lower())
                .first()
            )
            if not profile:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lawyer profile not found.")
            return LawyerFollowersResponse(
                handle=profile.handle,
                follower_count=self._follower_count(session, profile.id),
                followers=self._load_followers(session, profile.id, limit=limit),
            )
        finally:
            session.close()

    def toggle_follow(self, handle: str, current_user: User) -> LawyerFollowToggleResponse:
        session = SessionLocal()
        try:
            self._ensure_seed_data(session)
            normalized_handle = self._normalize_handle(handle)
            profile = (
                session.query(LawyerProfile)
                .filter(func.lower(LawyerProfile.handle) == normalized_handle.lower())
                .first()
            )
            if not profile:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lawyer profile not found.")
            if profile.user_id and profile.user_id == current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="You cannot follow your own lawyer profile.",
                )
            existing = (
                session.query(LawyerFollow)
                .filter(
                    LawyerFollow.lawyer_profile_id == profile.id,
                    LawyerFollow.user_id == current_user.id,
                )
                .first()
            )
            following = False
            if existing:
                session.delete(existing)
            else:
                session.add(
                    LawyerFollow(
                        lawyer_profile_id=profile.id,
                        user_id=current_user.id,
                        created_at=datetime.utcnow(),
                    )
                )
                following = True
            session.commit()
            return LawyerFollowToggleResponse(
                handle=profile.handle,
                following=following,
                follower_count=self._follower_count(session, profile.id),
                followers=self._load_followers(session, profile.id, limit=25),
            )
        finally:
            session.close()

    def toggle_post_like(self, post_id: int, current_user: User) -> LawyerPostLikeToggleResponse:
        session = SessionLocal()
        try:
            self._ensure_seed_data(session)
            post = session.get(LawyerPost, post_id)
            if not post:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lawyer post not found.")
            existing = (
                session.query(LawyerPostLike)
                .filter(LawyerPostLike.lawyer_post_id == post.id, LawyerPostLike.user_id == current_user.id)
                .first()
            )
            liked = False
            if existing:
                session.delete(existing)
            else:
                session.add(
                    LawyerPostLike(
                        lawyer_post_id=post.id,
                        user_id=current_user.id,
                        created_at=datetime.utcnow(),
                    )
                )
                liked = True
            session.flush()
            post.like_count = self._post_like_count(session, post.id)
            post.updated_at = datetime.utcnow()
            session.add(post)
            session.commit()
            return LawyerPostLikeToggleResponse(
                post_id=post.id,
                liked=liked,
                like_count=post.like_count,
                liked_by=self._load_post_likes(session, post.id, limit=25),
            )
        finally:
            session.close()

    def create_network_post(
        self,
        payload: LawyerNetworkPostCreateRequest,
        current_user: User,
    ) -> LawyerNetworkPostResponse:
        session = SessionLocal()
        try:
            self._ensure_seed_data(session)
            profile = session.query(LawyerProfile).filter(LawyerProfile.user_id == current_user.id).first()
            if not profile:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Create your lawyer profile before publishing to the network.",
                )
            if current_user.role != "lawyer" or current_user.approval_status != "approved":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only approved lawyer accounts can publish to the lawyer network.",
                )
            now = datetime.utcnow()
            post = LawyerPost(
                lawyer_profile_id=profile.id,
                post_kind="feed",
                category=payload.category.strip(),
                title=payload.title.strip(),
                excerpt=payload.excerpt.strip(),
                content=(payload.content.strip() if payload.content else payload.excerpt.strip()),
                like_count=0,
                comment_count=0,
                created_at=now,
                updated_at=now,
            )
            session.add(post)
            session.commit()
            session.refresh(post)
            return self._serialize_post(session, post, profile, is_liked=False)
        finally:
            session.close()

    def register_profile(
        self,
        payload: LawyerRegistrationRequest,
        current_user: User | None = None,
    ) -> LawyerRegistrationResponse:
        session = SessionLocal()
        try:
            self._ensure_seed_data(session)
            normalized_handle = self._normalize_handle(payload.handle)
            existing_handle = (
                session.query(LawyerProfile)
                .filter(func.lower(LawyerProfile.handle) == normalized_handle.lower())
                .first()
            )
            if existing_handle:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="That lawyer handle is already taken.",
                )
            if current_user:
                existing_profile = (
                    session.query(LawyerProfile)
                    .filter(LawyerProfile.user_id == current_user.id)
                    .first()
                )
                if existing_profile:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="This account already has a lawyer profile.",
                    )

            now = datetime.utcnow()
            profile = LawyerProfile(
                user_id=current_user.id if current_user else None,
                handle=normalized_handle,
                name=payload.name.strip(),
                bar_council_id=payload.bar_council_id.strip(),
                years_of_practice=payload.years_of_practice,
                specialization=payload.specialization.strip(),
                courts_practiced_in=payload.courts_practiced_in.strip(),
                city=payload.city.strip(),
                languages_json=json.dumps(self._clean_list(payload.languages), ensure_ascii=True),
                consultation_fee=payload.consultation_fee.strip(),
                profile_photo_url=(payload.profile_photo_url.strip() if payload.profile_photo_url else None),
                bio=payload.bio.strip(),
                about=(payload.about.strip() if payload.about else payload.bio.strip()),
                case_experience_json=json.dumps(self._clean_list(payload.case_experience), ensure_ascii=True),
                verification_status="pending",
                verified=False,
                rating_average=0.0,
                review_count=0,
                created_at=now,
                updated_at=now,
            )
            session.add(profile)
            if current_user:
                current_user.requested_role = "lawyer"
                current_user.approval_status = "pending" if current_user.role != "lawyer" else current_user.approval_status
                current_user.professional_id = payload.bar_council_id.strip()
                current_user.organization = payload.courts_practiced_in.strip()
                current_user.city = payload.city.strip()
                current_user.updated_at = now
                session.add(current_user)
            session.commit()
            session.refresh(profile)
            return LawyerRegistrationResponse(
                profile=self._serialize_profile_detail(
                    profile,
                    reviews=[],
                    articles=[],
                    followers=[],
                    follower_count=0,
                    article_count=0,
                    is_following=False,
                ),
            )
        finally:
            session.close()

    def get_lawyer_dashboard(self, current_user: User) -> LawyerDashboardResponse:
        session = SessionLocal()
        try:
            self._ensure_seed_data(session)
            if current_user.role != "lawyer" or current_user.approval_status != "approved":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This dashboard is available only to approved lawyer accounts.",
                )
            profile = session.query(LawyerProfile).filter(LawyerProfile.user_id == current_user.id).first()
            if not profile:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This dashboard is available after a lawyer profile is linked to your account.",
                )
            recent_followers = self._load_followers(session, profile.id, limit=8)
            feed_posts = (
                session.query(LawyerPost)
                .filter(LawyerPost.lawyer_profile_id == profile.id, LawyerPost.post_kind == "feed")
                .order_by(LawyerPost.like_count.desc(), LawyerPost.created_at.desc())
                .limit(5)
                .all()
            )
            dashboard_conversations = self._load_dashboard_conversations(session, current_user.id, limit=50)
            metrics = [
                LawyerDashboardMetricResponse(
                    title="Followers",
                    value=str(self._follower_count(session, profile.id)),
                    detail="Public followers across citizens, police officers, and lawyers.",
                ),
                LawyerDashboardMetricResponse(
                    title="New This Week",
                    value=str(
                        session.query(func.count(LawyerFollow.id))
                        .filter(
                            LawyerFollow.lawyer_profile_id == profile.id,
                            LawyerFollow.created_at >= datetime.utcnow() - timedelta(days=7),
                        )
                        .scalar()
                        or 0
                    ),
                    detail="New audience growth from live follow activity.",
                ),
                LawyerDashboardMetricResponse(
                    title="Post Likes",
                    value=str(sum(post.like_count for post in feed_posts)),
                    detail="Real engagement captured from users liking your network posts.",
                ),
                LawyerDashboardMetricResponse(
                    title="Active Conversations",
                    value=str(len(dashboard_conversations)),
                    detail="Direct citizen and professional chats currently linked to your account.",
                ),
            ]
            return LawyerDashboardResponse(
                metrics=metrics,
                recent_followers=recent_followers,
                top_posts=[self._serialize_post(session, post, profile, is_liked=False) for post in feed_posts],
                recent_conversations=dashboard_conversations[:6],
                generated_at=datetime.utcnow(),
            )
        finally:
            session.close()

    def get_police_dashboard(self, limit: int = 8) -> PoliceDashboardResponse:
        records = self.fir_service.list_records(limit=limit)
        patterns = self.fir_service.crime_patterns(window_days=7)
        queue = [self._serialize_queue_item(record) for record in records.records]
        cards = [
            PoliceDashboardCardResponse(
                title="Complaint Review Queue",
                value=f"{len(queue)} pending",
                detail="Recent FIR drafts and complaint records available for police review.",
            ),
            PoliceDashboardCardResponse(
                title="Voice FIR Drafts",
                value=f"{sum(1 for item in records.records if item.workflow == 'voice')} generated",
                detail="Voice complaint workflows converted into structured FIR drafts.",
            ),
            PoliceDashboardCardResponse(
                title="Hotspot Signals",
                value=f"{len(patterns.hotspot_alerts)} active zones",
                detail="Location and crime-category clusters identified from recent FIR records.",
            ),
            PoliceDashboardCardResponse(
                title="Case Tracking",
                value=f"{len(records.records)} live",
                detail="Latest complaint drafts available with timestamps and strength indicators.",
            ),
        ]
        hotspot_alerts = [
            PoliceHotspotAlertResponse(
                title=f"{alert.crime_category} - {alert.location}",
                detail=alert.insight,
            )
            for alert in patterns.hotspot_alerts
        ]
        return PoliceDashboardResponse(
            cards=cards,
            queue=queue,
            hotspot_alerts=hotspot_alerts,
            generated_at=datetime.utcnow(),
        )

    def _serialize_queue_item(self, record: FIRRecordSummary) -> PoliceQueueItemResponse:
        title = f"{record.workflow.title()} FIR - {record.incident_location or record.police_station or 'Location pending'}"
        detail = record.draft_excerpt.strip()
        if len(detail) > 160:
            detail = f"{detail[:157]}..."
        return PoliceQueueItemResponse(
            fir_id=record.fir_id,
            title=title,
            status=record.status.replace("_", " ").title(),
            detail=detail,
            workflow=record.workflow,
            police_station=record.police_station,
            last_edited_at=record.last_edited_at,
        )

    def _serialize_profile_summary(
        self,
        profile: LawyerProfile,
        follower_count: int = 0,
        article_count: int = 0,
    ) -> LawyerProfileSummaryResponse:
        languages = self._load_json_list(profile.languages_json)
        return LawyerProfileSummaryResponse(
            handle=profile.handle,
            name=profile.name,
            bar_council_id=profile.bar_council_id,
            years_of_practice=profile.years_of_practice,
            experience=self._experience_label(profile.years_of_practice),
            specialization=profile.specialization,
            courts=profile.courts_practiced_in,
            city=profile.city,
            languages=languages,
            fee=profile.consultation_fee,
            rating=round(profile.rating_average or 0.0, 1),
            review_count=profile.review_count,
            bio=profile.bio,
            verified=profile.verified,
            verification_status=profile.verification_status,
            follower_count=follower_count,
            article_count=article_count,
            public_url=f"nyayasetu.in/lawyer/@{profile.handle}",
        )

    def _serialize_profile_detail(
        self,
        profile: LawyerProfile,
        reviews: list[LawyerReview],
        articles: list[LawyerPost],
        followers: list[LawyerFollowerResponse],
        follower_count: int,
        article_count: int,
        is_following: bool,
    ) -> LawyerProfileDetailResponse:
        summary = self._serialize_profile_summary(
            profile,
            follower_count=follower_count,
            article_count=article_count,
        )
        return LawyerProfileDetailResponse(
            **summary.model_dump(),
            about=profile.about,
            case_experience=self._load_json_list(profile.case_experience_json),
            reviews=[
                LawyerReviewResponse(
                    author=row.author_name,
                    text=row.review_text,
                    rating=row.rating,
                    created_at=row.created_at.isoformat(),
                )
                for row in reviews
            ],
            articles=[
                LawyerArticleResponse(
                    category=row.category,
                    title=row.title,
                    excerpt=row.excerpt,
                    created_at=row.created_at.isoformat(),
                )
                for row in articles
            ],
            followers=followers,
            is_following=is_following,
            messaging_enabled=bool(profile.user_id),
            created_at=profile.created_at.isoformat(),
            updated_at=profile.updated_at.isoformat(),
        )

    def _serialize_post(
        self,
        session,
        post: LawyerPost,
        profile: LawyerProfile,
        is_liked: bool = False,
    ) -> LawyerNetworkPostResponse:
        return LawyerNetworkPostResponse(
            id=post.id,
            handle=profile.handle,
            author=profile.name,
            category=post.category,
            title=post.title,
            excerpt=post.excerpt,
            like_count=post.like_count,
            comment_count=post.comment_count,
            stats=f"{post.like_count} likes | {post.comment_count} comments",
            liked_by=self._load_post_likes(session, post.id, limit=12),
            is_liked=is_liked,
            public_url=f"nyayasetu.in/lawyer/@{profile.handle}",
            created_at=post.created_at.isoformat(),
        )

    def _load_followers(self, session, lawyer_profile_id: int, limit: int = 25) -> list[LawyerFollowerResponse]:
        rows = (
            session.query(LawyerFollow, User)
            .join(User, User.id == LawyerFollow.user_id)
            .filter(LawyerFollow.lawyer_profile_id == lawyer_profile_id)
            .order_by(LawyerFollow.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            LawyerFollowerResponse(
                name=user.full_name,
                role=user.role,
                followed_at=follow.created_at.isoformat(),
            )
            for follow, user in rows
        ]

    def _load_post_likes(self, session, post_id: int, limit: int = 25) -> list[LawyerPostLikeResponse]:
        rows = (
            session.query(LawyerPostLike, User)
            .join(User, User.id == LawyerPostLike.user_id)
            .filter(LawyerPostLike.lawyer_post_id == post_id)
            .order_by(LawyerPostLike.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            LawyerPostLikeResponse(
                name=user.full_name,
                role=user.role,
                liked_at=like.created_at.isoformat(),
            )
            for like, user in rows
        ]

    def _follower_count(self, session, lawyer_profile_id: int) -> int:
        return int(
            session.query(func.count(LawyerFollow.id))
            .filter(LawyerFollow.lawyer_profile_id == lawyer_profile_id)
            .scalar()
            or 0
        )

    def _follower_counts(self, session, lawyer_profile_ids: list[int]) -> dict[int, int]:
        if not lawyer_profile_ids:
            return {}
        rows = (
            session.query(LawyerFollow.lawyer_profile_id, func.count(LawyerFollow.id))
            .filter(LawyerFollow.lawyer_profile_id.in_(lawyer_profile_ids))
            .group_by(LawyerFollow.lawyer_profile_id)
            .all()
        )
        return {profile_id: int(count) for profile_id, count in rows}

    def _article_count(self, session, lawyer_profile_id: int) -> int:
        return int(
            session.query(func.count(LawyerPost.id))
            .filter(LawyerPost.lawyer_profile_id == lawyer_profile_id, LawyerPost.post_kind == "article")
            .scalar()
            or 0
        )

    def _article_counts(self, session, lawyer_profile_ids: list[int]) -> dict[int, int]:
        if not lawyer_profile_ids:
            return {}
        rows = (
            session.query(LawyerPost.lawyer_profile_id, func.count(LawyerPost.id))
            .filter(LawyerPost.lawyer_profile_id.in_(lawyer_profile_ids), LawyerPost.post_kind == "article")
            .group_by(LawyerPost.lawyer_profile_id)
            .all()
        )
        return {profile_id: int(count) for profile_id, count in rows}

    def _post_like_count(self, session, post_id: int) -> int:
        return int(
            session.query(func.count(LawyerPostLike.id))
            .filter(LawyerPostLike.lawyer_post_id == post_id)
            .scalar()
            or 0
        )

    def _liked_post_ids(self, session, post_ids: list[int], user_id: str) -> set[int]:
        if not post_ids:
            return set()
        rows = (
            session.query(LawyerPostLike.lawyer_post_id)
            .filter(LawyerPostLike.user_id == user_id, LawyerPostLike.lawyer_post_id.in_(post_ids))
            .all()
        )
        return {int(row[0]) for row in rows}

    def _is_following(self, session, lawyer_profile_id: int, user_id: str) -> bool:
        return (
            session.query(LawyerFollow.id)
            .filter(LawyerFollow.lawyer_profile_id == lawyer_profile_id, LawyerFollow.user_id == user_id)
            .first()
            is not None
        )

    def _load_dashboard_conversations(
        self,
        session,
        user_id: str,
        limit: int = 6,
    ) -> list[LawyerDashboardConversationResponse]:
        rows = (
            session.query(DirectConversation)
            .filter(
                or_(
                    DirectConversation.participant_a_id == user_id,
                    DirectConversation.participant_b_id == user_id,
                )
            )
            .order_by(DirectConversation.last_message_at.desc().nullslast(), DirectConversation.updated_at.desc())
            .limit(limit)
            .all()
        )
        conversation_ids = [row.id for row in rows]
        counterpart_ids = [
            row.participant_b_id if row.participant_a_id == user_id else row.participant_a_id
            for row in rows
        ]
        counterparts = session.query(User).filter(User.id.in_(counterpart_ids)).all() if counterpart_ids else []
        counterparts_by_id = {counterpart.id: counterpart for counterpart in counterparts}
        unread_counts: dict[int, int] = {}
        if conversation_ids:
            unread_rows = (
                session.query(DirectMessage.conversation_id, func.count(DirectMessage.id))
                .filter(
                    DirectMessage.conversation_id.in_(conversation_ids),
                    DirectMessage.recipient_user_id == user_id,
                    DirectMessage.read_at.is_(None),
                )
                .group_by(DirectMessage.conversation_id)
                .all()
            )
            unread_counts = {int(conversation_id): int(count) for conversation_id, count in unread_rows}
        items: list[LawyerDashboardConversationResponse] = []
        for row in rows:
            counterpart_id = row.participant_b_id if row.participant_a_id == user_id else row.participant_a_id
            counterpart = counterparts_by_id.get(counterpart_id)
            if not counterpart:
                continue
            items.append(
                LawyerDashboardConversationResponse(
                    conversation_id=row.id,
                    counterpart_name=counterpart.full_name,
                    counterpart_role=counterpart.role,
                    preview=row.last_message_preview or "Conversation started",
                    unread_count=unread_counts.get(row.id, 0),
                    last_message_at=row.last_message_at.isoformat() if row.last_message_at else None,
                )
            )
        return items

    def _ensure_seed_data(self, session) -> None:
        if self._seed_checked:
            return
        existing = session.query(LawyerProfile.id).limit(1).first()
        if existing:
            self._seed_checked = True
            return

        now = datetime.utcnow()
        seed_users = [
            {
                "id": "seed-citizen-priya",
                "email": "priya.nair.demo@nyayasetu.local",
                "full_name": "Priya Nair",
                "role": "citizen",
            },
            {
                "id": "seed-police-arjun",
                "email": "arjun.rao.demo@nyayasetu.local",
                "full_name": "Inspector Arjun Rao",
                "role": "police",
            },
            {
                "id": "seed-lawyer-meera",
                "email": "meera.kapoor.demo@nyayasetu.local",
                "full_name": "Advocate Meera Kapoor",
                "role": "lawyer",
            },
            {
                "id": "seed-citizen-kabir",
                "email": "kabir.singh.demo@nyayasetu.local",
                "full_name": "Kabir Singh",
                "role": "citizen",
            },
        ]
        for item in seed_users:
            session.add(
                User(
                    id=item["id"],
                    email=item["email"],
                    full_name=item["full_name"],
                    role=item["role"],
                    password_hash=self._seed_password_hash(item["email"]),
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )

        seeded_profile_ids: dict[str, int] = {}
        seeded_post_ids: dict[str, list[int]] = {}
        seeded_profiles = [
            {
                "handle": "adv_sharma",
                "name": "Advocate Ananya Sharma",
                "bar_council_id": "D/1234/2016",
                "years_of_practice": 8,
                "specialization": "Criminal Law",
                "courts_practiced_in": "Delhi High Court, Tis Hazari Courts",
                "city": "New Delhi",
                "languages": ["English", "Hindi"],
                "consultation_fee": "INR 2,500",
                "bio": "Criminal law strategist focused on cyber fraud, bail hearings, and victim-oriented complaint workflows.",
                "about": "Ananya works on complex criminal complaints, anticipatory bail strategy, and digital evidence review for citizens navigating early-stage police process.",
                "case_experience": [
                    "Led pre-FIR advisory for cyber intimidation and extortion complaints.",
                    "Represented clients in Delhi High Court bail and quashing matters.",
                    "Advises startups and women-led founders on digital harassment response.",
                ],
                "verified": True,
                "verification_status": "verified",
                "reviews": [
                    ("Ritika M.", "Explained the complaint process clearly and helped us preserve evidence properly.", 5),
                    ("Vikram S.", "Very strong on criminal drafting and practical next steps.", 5),
                ],
                "posts": [
                    (
                        "feed",
                        "Judgment Insight",
                        "How courts are reading digital evidence in early criminal proceedings",
                        "Screenshots alone rarely tell the full story. The stronger complaint bundles metadata, chronology, and source preservation right from the first filing.",
                        128,
                        24,
                    ),
                    (
                        "article",
                        "Article",
                        "How to preserve WhatsApp evidence before filing a complaint",
                        "A practical checklist for screenshots, exports, device metadata, and timeline capture.",
                        42,
                        6,
                    ),
                    (
                        "article",
                        "Article",
                        "When should a cyber intimidation complaint become an FIR request?",
                        "Understanding escalation points, urgency, and supporting materials.",
                        33,
                        4,
                    ),
                ],
            },
            {
                "handle": "justice_rohan",
                "name": "Advocate Rohan Mehta",
                "bar_council_id": "MH/8841/2013",
                "years_of_practice": 11,
                "specialization": "Cyber Crime",
                "courts_practiced_in": "Mumbai Sessions Court, Bombay High Court",
                "city": "Mumbai",
                "languages": ["English", "Hindi", "Marathi"],
                "consultation_fee": "INR 3,000",
                "bio": "Cybercrime litigator helping citizens and enterprises respond to phishing, OTP fraud, and digital extortion.",
                "about": "Rohan focuses on financial cybercrime, device seizure readiness, and building strong documentary trails for investigation agencies.",
                "case_experience": [
                    "Handled OTP theft and online banking fraud advisory matters.",
                    "Supports e-evidence compilation and Section 65B readiness.",
                    "Works with police teams on digital complaint triage.",
                ],
                "verified": True,
                "verification_status": "verified",
                "reviews": [
                    ("Anuj P.", "Excellent understanding of cyber evidence and bank complaint timelines.", 5),
                    ("Megha R.", "Very practical and fast to respond in urgent fraud cases.", 4),
                ],
                "posts": [
                    (
                        "feed",
                        "Citizen Q&A",
                        "What should a victim preserve after OTP fraud?",
                        "Start with the call log, SMS alerts, device details, complaint number, and the exact timeline of disclosure and debit events.",
                        94,
                        17,
                    ),
                    (
                        "article",
                        "Article",
                        "What victims should preserve after OTP fraud",
                        "Beyond statements: preserve call records, device details, complaint IDs, and messaging trails.",
                        29,
                        5,
                    ),
                    (
                        "article",
                        "Article",
                        "Building a stronger cyber complaint with transaction metadata",
                        "How early evidence improves both police action and recovery chances.",
                        21,
                        3,
                    ),
                ],
            },
            {
                "handle": "legal_saba",
                "name": "Advocate Saba Khan",
                "bar_council_id": "UP/4472/2018",
                "years_of_practice": 6,
                "specialization": "Family & Property",
                "courts_practiced_in": "Lucknow Bench, District Civil Courts",
                "city": "Lucknow",
                "languages": ["English", "Hindi", "Urdu"],
                "consultation_fee": "INR 1,800",
                "bio": "Property and family law practitioner focused on plain-language legal access for citizens.",
                "about": "Saba works on tenancy disputes, domestic relief strategy, and property possession issues with a strong emphasis on documentation and citizen education.",
                "case_experience": [
                    "Assisted tenants with deposit recovery and legal notice strategy.",
                    "Works on family settlement and maintenance matters.",
                    "Known for citizen-friendly legal explainers and local court navigation.",
                ],
                "verified": True,
                "verification_status": "verified",
                "reviews": [
                    ("Farah A.", "Helped me understand my landlord dispute without jargon.", 5),
                    ("Rohit K.", "Very professional and patient with documentation review.", 4),
                ],
                "posts": [
                    (
                        "feed",
                        "Bare Act Thread",
                        "Tenant deposit disputes: when should negotiation end and legal notice begin?",
                        "If the landlord is delaying beyond a documented timeline and refusing clear communication, preserve the trail and prepare a notice strategy early.",
                        73,
                        11,
                    ),
                    (
                        "article",
                        "Article",
                        "When should a tenant send a legal notice for deposit recovery?",
                        "How to move from negotiation to formal legal action with a clean paper trail.",
                        18,
                        2,
                    ),
                    (
                        "article",
                        "Article",
                        "Property dispute checklists citizens should maintain",
                        "An evidence-first guide for notices, possession, and civil filing readiness.",
                        16,
                        2,
                    ),
                ],
            },
        ]

        for item in seeded_profiles:
            review_values = item.pop("reviews")
            post_values = item.pop("posts")
            profile = LawyerProfile(
                handle=item["handle"],
                name=item["name"],
                bar_council_id=item["bar_council_id"],
                years_of_practice=item["years_of_practice"],
                specialization=item["specialization"],
                courts_practiced_in=item["courts_practiced_in"],
                city=item["city"],
                languages_json=json.dumps(item["languages"], ensure_ascii=True),
                consultation_fee=item["consultation_fee"],
                bio=item["bio"],
                about=item["about"],
                case_experience_json=json.dumps(item["case_experience"], ensure_ascii=True),
                verified=item["verified"],
                verification_status=item["verification_status"],
                rating_average=0.0,
                review_count=0,
                created_at=now,
                updated_at=now,
            )
            session.add(profile)
            session.flush()
            seeded_profile_ids[profile.handle] = profile.id
            seeded_post_ids[profile.handle] = []

            ratings: list[int] = []
            for author_name, review_text, rating in review_values:
                ratings.append(rating)
                session.add(
                    LawyerReview(
                        lawyer_profile_id=profile.id,
                        author_name=author_name,
                        review_text=review_text,
                        rating=rating,
                        created_at=now,
                    )
                )
            for post_kind, category, title, excerpt, like_count, comment_count in post_values:
                post = LawyerPost(
                    lawyer_profile_id=profile.id,
                    post_kind=post_kind,
                    category=category,
                    title=title,
                    excerpt=excerpt,
                    content=excerpt,
                    like_count=like_count,
                    comment_count=comment_count,
                    created_at=now,
                    updated_at=now,
                )
                session.add(post)
                session.flush()
                seeded_post_ids[profile.handle].append(post.id)
            profile.review_count = len(ratings)
            profile.rating_average = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
            session.add(profile)

        seed_follows = [
            ("adv_sharma", "seed-citizen-priya"),
            ("adv_sharma", "seed-police-arjun"),
            ("justice_rohan", "seed-citizen-kabir"),
            ("justice_rohan", "seed-lawyer-meera"),
            ("legal_saba", "seed-citizen-priya"),
        ]
        for handle, user_id in seed_follows:
            session.add(
                LawyerFollow(
                    lawyer_profile_id=seeded_profile_ids[handle],
                    user_id=user_id,
                    created_at=now,
                )
            )

        seed_likes = [
            ("adv_sharma", 0, "seed-citizen-priya"),
            ("adv_sharma", 0, "seed-police-arjun"),
            ("justice_rohan", 0, "seed-citizen-kabir"),
            ("justice_rohan", 0, "seed-lawyer-meera"),
            ("legal_saba", 0, "seed-citizen-priya"),
        ]
        for handle, post_index, user_id in seed_likes:
            session.add(
                LawyerPostLike(
                    lawyer_post_id=seeded_post_ids[handle][post_index],
                    user_id=user_id,
                    created_at=now,
                )
            )

        session.flush()
        for post_ids in seeded_post_ids.values():
            for post_id in post_ids:
                post = session.get(LawyerPost, post_id)
                if post:
                    post.like_count = self._post_like_count(session, post_id)
                    session.add(post)

        session.commit()
        self._seed_checked = True

    def _normalize_handle(self, handle: str) -> str:
        normalized = handle.strip().lower()
        if normalized.startswith("@"):
            normalized = normalized[1:]
        normalized = normalized.replace(" ", "_")
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Lawyer handle is required.",
            )
        return normalized

    def _clean_list(self, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value and value.strip()]

    def _load_json_list(self, raw_value: str | None) -> list[str]:
        if not raw_value:
            return []
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            return []
        return [str(item) for item in parsed if str(item).strip()]

    def _experience_label(self, years_of_practice: int) -> str:
        year_word = "year" if years_of_practice == 1 else "years"
        return f"{years_of_practice} {year_word}"

    def _seed_password_hash(self, seed_value: str) -> str:
        salt = hashlib.sha256(f"{seed_value}-salt".encode("utf-8")).hexdigest()[:32]
        iterations = 390000
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            f"{seed_value}-demo-pass".encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
        return f"pbkdf2_sha256${iterations}${salt}${digest}"
