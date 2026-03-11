from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine_kwargs: dict = {"future": True}
if settings.resolved_database_connect_args:
    engine_kwargs["connect_args"] = settings.resolved_database_connect_args
if settings.resolved_database_url.startswith("sqlite+libsql://"):
    engine_kwargs["pool_pre_ping"] = True
engine = create_engine(settings.resolved_database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models.audit import AuditLog
    from app.models.auth import AuthSession, User
    from app.models.fir import FIREvidence, FIRRecord, FIRVersion

    Base.metadata.create_all(bind=engine)
