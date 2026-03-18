from collections.abc import Generator

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import NoSuchModuleError
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
try:
    engine = create_engine(settings.resolved_database_url, **engine_kwargs)
except NoSuchModuleError:
    fallback_url = f"sqlite+pysqlite:///{settings.app_sqlite_path.resolve().as_posix()}"
    fallback_kwargs = {"future": True, "connect_args": {"check_same_thread": False}}
    engine = create_engine(fallback_url, **fallback_kwargs)
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
    from app.models.fir import FIREvidence, FIRIntelligence, FIRRecord, FIRVersion
    from app.models.lawyer import LawyerFollow, LawyerPost, LawyerPostLike, LawyerProfile, LawyerReview
    from app.models.messaging import DirectConversation, DirectMessage

    Base.metadata.create_all(bind=engine)
    _ensure_column("users", "requested_role", "VARCHAR(64) NOT NULL DEFAULT 'citizen'")
    _ensure_column("users", "approval_status", "VARCHAR(32) NOT NULL DEFAULT 'approved'")
    _ensure_column("users", "professional_id", "VARCHAR(128)")
    _ensure_column("users", "organization", "VARCHAR(255)")
    _ensure_column("users", "city", "VARCHAR(128)")
    _ensure_column("users", "preferred_language", "VARCHAR(32) NOT NULL DEFAULT 'en'")
    _ensure_column("users", "approval_notes", "TEXT")
    _ensure_column("users", "approval_updated_at", "DATETIME")
    _ensure_column("fir_records", "draft_role", "VARCHAR(48) NOT NULL DEFAULT 'citizen_application'")
    _ensure_column("fir_records", "draft_language", "VARCHAR(32) NOT NULL DEFAULT 'en'")
    _ensure_column("fir_records", "comparative_sections", "TEXT")
    _ensure_column("fir_records", "citizen_application_text", "TEXT")
    _ensure_column("fir_records", "police_fir_text", "TEXT")
    _ensure_column("fir_records", "lawyer_analysis_text", "TEXT")
    _ensure_column("fir_records", "source_application_text", "TEXT")
    _ensure_column("fir_versions", "document_kind", "VARCHAR(48) NOT NULL DEFAULT 'citizen_application'")
    _ensure_column("fir_versions", "language", "VARCHAR(32) NOT NULL DEFAULT 'en'")


def _ensure_column(table_name: str, column_name: str, ddl: str) -> None:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return
    column_names = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in column_names:
        return
    with engine.begin() as connection:
        connection.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")
