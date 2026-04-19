from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import logging
import threading

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import NoSuchModuleError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
logger = logging.getLogger(__name__)
engine_kwargs: dict = {"future": True}
if settings.resolved_database_connect_args:
    engine_kwargs["connect_args"] = settings.resolved_database_connect_args
if settings.resolved_database_url.startswith("sqlite+libsql://"):
    engine_kwargs["pool_pre_ping"] = True
fallback_url = f"sqlite+pysqlite:///{settings.app_sqlite_path.resolve().as_posix()}"
fallback_kwargs = {"future": True, "connect_args": {"check_same_thread": False}}
_db_init_lock = threading.Lock()
_db_initialized = False


def _build_sqlite_fallback_engine():
    logger.warning("Using local SQLite fallback database at %s", settings.app_sqlite_path)
    return create_engine(fallback_url, **fallback_kwargs)


def _ping_engine(candidate_engine) -> None:
    with candidate_engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def _engine_responds(candidate_engine) -> bool:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_ping_engine, candidate_engine)
    try:
        future.result(timeout=settings.database_probe_timeout_seconds)
        executor.shutdown(wait=False, cancel_futures=True)
        return True
    except FuturesTimeoutError:
        logger.warning(
            "Database probe exceeded %.1fs. Falling back to local SQLite.",
            settings.database_probe_timeout_seconds,
        )
        executor.shutdown(wait=False, cancel_futures=True)
        return False
    except SQLAlchemyError as exc:
        logger.warning("Database probe failed: %s. Falling back to local SQLite.", exc)
        executor.shutdown(wait=False, cancel_futures=True)
        return False
    except Exception as exc:  # pragma: no cover - defensive fallback for hosted DB drivers
        logger.warning("Unexpected database probe failure: %s. Falling back to local SQLite.", exc)
        executor.shutdown(wait=False, cancel_futures=True)
        return False


try:
    if settings.space_local_app_db_fallback_reason:
        logger.warning(
            "Running on Hugging Face Space with %s. Using SQLite fallback.",
            settings.space_local_app_db_fallback_reason,
        )
        engine = _build_sqlite_fallback_engine()
    else:
        engine = create_engine(settings.resolved_database_url, **engine_kwargs)
    if settings.resolved_database_url.startswith("sqlite+libsql://") and engine.url.drivername == "sqlite+libsql" and not _engine_responds(engine):
        engine.dispose()
        engine = _build_sqlite_fallback_engine()
except NoSuchModuleError:
    engine = _build_sqlite_fallback_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    global _db_initialized
    if _db_initialized:
        return
    with _db_init_lock:
        if _db_initialized:
            return

        from app.models.audit import AuditLog
        from app.models.auth import AuthSession, User
        from app.models.documents import DocumentOrder, DocumentTemplate
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
        _ensure_index("ix_users_email_fast_lookup", "users", ["email"], unique=True)
        _ensure_index("ix_users_role_approval_lookup", "users", ["requested_role", "approval_status"])
        _ensure_index("ix_auth_sessions_token_hash_fast_lookup", "auth_sessions", ["token_hash"], unique=True)
        _ensure_index("ix_auth_sessions_user_id_created_at", "auth_sessions", ["user_id", "created_at"])
        _ensure_index("ix_auth_sessions_revoked_expires", "auth_sessions", ["revoked_at", "expires_at"])
        _db_initialized = True


def _ensure_column(table_name: str, column_name: str, ddl: str) -> None:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return
    column_names = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in column_names:
        return
    with engine.begin() as connection:
        connection.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")


def _ensure_index(index_name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return
    existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name in existing_indexes:
        return
    unique_sql = "UNIQUE " if unique else ""
    column_sql = ", ".join(columns)
    with engine.begin() as connection:
        connection.exec_driver_sql(f"CREATE {unique_sql}INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_sql})")
