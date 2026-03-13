from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LawyerProfile(Base):
    __tablename__ = "lawyer_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("users.id"),
        nullable=True,
        unique=True,
        index=True,
    )
    handle: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    bar_council_id: Mapped[str] = mapped_column(String(128), nullable=False)
    years_of_practice: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    specialization: Mapped[str] = mapped_column(String(255), nullable=False)
    courts_practiced_in: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    languages_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    consultation_fee: Mapped[str] = mapped_column(String(128), nullable=False)
    profile_photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    bio: Mapped[str] = mapped_column(Text, nullable=False)
    about: Mapped[str] = mapped_column(Text, nullable=False)
    case_experience_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rating_average: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class LawyerReview(Base):
    __tablename__ = "lawyer_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lawyer_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("lawyer_profiles.id"),
        nullable=False,
        index=True,
    )
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class LawyerPost(Base):
    __tablename__ = "lawyer_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lawyer_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("lawyer_profiles.id"),
        nullable=False,
        index=True,
    )
    post_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="feed")
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
