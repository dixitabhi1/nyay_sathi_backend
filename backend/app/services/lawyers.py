from __future__ import annotations

import json
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, or_

from app.db.session import SessionLocal
from app.models.auth import User
from app.models.lawyer import LawyerPost, LawyerProfile, LawyerReview
from app.schemas.fir import FIRRecordSummary
from app.schemas.lawyers import (
    LawyerArticleResponse,
    LawyerDirectoryResponse,
    LawyerNetworkFeedResponse,
    LawyerNetworkPostResponse,
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
            lawyers = [self._serialize_profile_summary(row) for row in rows]
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

    def get_profile(self, handle: str) -> LawyerProfileDetailResponse:
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
            return self._serialize_profile_detail(profile, reviews, articles)
        finally:
            session.close()

    def list_network_feed(self, limit: int = 20) -> LawyerNetworkFeedResponse:
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
            return LawyerNetworkFeedResponse(
                posts=[
                    LawyerNetworkPostResponse(
                        handle=profile.handle,
                        author=profile.name,
                        category=post.category,
                        title=post.title,
                        excerpt=post.excerpt,
                        like_count=post.like_count,
                        comment_count=post.comment_count,
                        stats=f"{post.like_count} likes | {post.comment_count} comments",
                        created_at=post.created_at.isoformat(),
                    )
                    for post, profile in rows
                ]
            )
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
            if current_user and current_user.role != "lawyer":
                current_user.role = "lawyer"
                current_user.updated_at = now
                session.add(current_user)
            session.commit()
            session.refresh(profile)
            return LawyerRegistrationResponse(
                profile=self._serialize_profile_detail(profile, reviews=[], articles=[]),
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

    def _serialize_profile_summary(self, profile: LawyerProfile) -> LawyerProfileSummaryResponse:
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
            public_url=f"nyayasetu.in/lawyer/@{profile.handle}",
        )

    def _serialize_profile_detail(
        self,
        profile: LawyerProfile,
        reviews: list[LawyerReview],
        articles: list[LawyerPost],
    ) -> LawyerProfileDetailResponse:
        summary = self._serialize_profile_summary(profile)
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
            created_at=profile.created_at.isoformat(),
            updated_at=profile.updated_at.isoformat(),
        )

    def _ensure_seed_data(self, session) -> None:
        existing = session.query(LawyerProfile.id).limit(1).first()
        if existing:
            return

        now = datetime.utcnow()
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
                session.add(
                    LawyerPost(
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
                )
            profile.review_count = len(ratings)
            profile.rating_average = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
            session.add(profile)

        session.commit()

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
