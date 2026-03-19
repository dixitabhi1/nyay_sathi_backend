from functools import lru_cache
from pathlib import Path
import secrets
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT_DIR / path


def resolve_storage_path(path: Path, storage_root: Path | None) -> Path:
    if path.is_absolute():
        return path
    if storage_root is not None:
        return storage_root / path
    return ROOT_DIR / path


def normalize_turso_database_url(raw_url: str) -> str:
    candidate = raw_url.strip()
    if not candidate:
        return candidate
    if candidate.startswith("sqlite+libsql://"):
        return _with_turso_remote_params(candidate)
    if candidate.startswith("libsql://"):
        return _with_turso_remote_params(f"sqlite+{candidate}")

    parsed = urlparse(candidate)
    if parsed.scheme in {"https", "http"} and parsed.netloc:
        return _with_turso_remote_params(f"sqlite+libsql://{parsed.netloc}")

    if "://" not in candidate:
        return _with_turso_remote_params(f"sqlite+libsql://{candidate.rstrip('/')}")

    return candidate


def _with_turso_remote_params(database_url: str) -> str:
    parsed = urlparse(database_url)
    if not parsed.netloc:
        return database_url

    query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query_items.setdefault("secure", "true")
    updated_query = urlencode(query_items)
    return urlunparse(parsed._replace(query=updated_query))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "NyayaSetu"
    app_env: str = Field(default="development", alias="APP_ENV")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_v1_prefix: str = "/api/v1"
    frontend_url: str = Field(default="http://localhost:5173", alias="FRONTEND_URL")
    auth_secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(48), alias="AUTH_SECRET_KEY")
    auth_token_ttl_hours: int = Field(default=24, alias="AUTH_TOKEN_TTL_HOURS")
    admin_emails: str = Field(default="", alias="ADMIN_EMAILS")
    database_probe_timeout_seconds: float = Field(default=4.0, alias="DATABASE_PROBE_TIMEOUT_SECONDS")
    persistent_storage_root: Path | None = Field(default=None, alias="PERSISTENT_STORAGE_ROOT")

    app_sqlite_path: Path = Field(default=Path("storage/db/nyayasetu.sqlite3"), alias="APP_SQLITE_PATH")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    turso_database_url: str | None = Field(default=None, alias="TURSO_DATABASE_URL")
    turso_auth_token: str | None = Field(default=None, alias="TURSO_AUTH_TOKEN")
    analytics_db_path: Path = Field(default=Path("data/analytics/legal_corpus.duckdb"), alias="ANALYTICS_DB_PATH")

    embedding_model_name: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        alias="EMBEDDING_MODEL_NAME",
    )
    vector_index_path: Path = Field(default=Path("data/index/legal.index"), alias="VECTOR_INDEX_PATH")
    vector_metadata_path: Path = Field(default=Path("data/index/legal_metadata.json"), alias="VECTOR_METADATA_PATH")
    page_index_path: Path = Field(default=Path("data/index/legal_page_index.json"), alias="PAGE_INDEX_PATH")
    legal_corpus_path: Path = Field(
        default=ROOT_DIR / "data" / "corpus" / "official_legal_corpus.jsonl",
        alias="LEGAL_CORPUS_PATH",
    )
    bootstrap_corpus_path: Path = Field(
        default=ROOT_DIR / "data" / "sample" / "legal_corpus" / "legal_corpus.jsonl",
        alias="BOOTSTRAP_CORPUS_PATH",
    )
    official_sources_manifest_path: Path = Field(
        default=ROOT_DIR / "ingestion" / "configs" / "official_sources.json",
        alias="OFFICIAL_SOURCES_MANIFEST_PATH",
    )
    jurisdiction_gazetteer_path: Path = Field(
        default=ROOT_DIR / "data" / "sample" / "police_jurisdictions.json",
        alias="JURISDICTION_GAZETTEER_PATH",
    )
    top_k_retrieval: int = Field(default=4, alias="TOP_K_RETRIEVAL")
    page_index_top_k: int = Field(default=6, alias="PAGE_INDEX_TOP_K")
    legal_scope_anchor_threshold: float = Field(default=0.34, alias="LEGAL_SCOPE_ANCHOR_THRESHOLD")
    legal_scope_margin: float = Field(default=0.03, alias="LEGAL_SCOPE_MARGIN")
    legal_scope_corpus_threshold: float = Field(default=0.43, alias="LEGAL_SCOPE_CORPUS_THRESHOLD")
    page_index_scope_threshold: float = Field(default=0.48, alias="PAGE_INDEX_SCOPE_THRESHOLD")
    hybrid_semantic_weight: float = Field(default=0.55, alias="HYBRID_SEMANTIC_WEIGHT")
    hybrid_page_index_weight: float = Field(default=0.35, alias="HYBRID_PAGE_INDEX_WEIGHT")
    hybrid_cross_signal_bonus: float = Field(default=0.08, alias="HYBRID_CROSS_SIGNAL_BONUS")
    hybrid_exact_reference_bonus: float = Field(default=0.12, alias="HYBRID_EXACT_REFERENCE_BONUS")

    inference_provider: str = Field(default="mock", alias="INFERENCE_PROVIDER")
    inference_base_url: str = Field(default="http://localhost:8000/v1", alias="INFERENCE_BASE_URL")
    inference_model_name: str = Field(default="/models/mistral-7b-instruct", alias="INFERENCE_MODEL_NAME")
    local_model_name: str = Field(default="microsoft/Phi-3-mini-4k-instruct", alias="LOCAL_MODEL_NAME")
    bns_classifier_model_name: str = Field(default="", alias="BNS_CLASSIFIER_MODEL_NAME")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1:8b-instruct-q4_K_M", alias="OLLAMA_MODEL")
    max_generation_tokens: int = Field(default=768, alias="MAX_GENERATION_TOKENS")
    temperature: float = Field(default=0.2, alias="TEMPERATURE")
    inference_timeout_seconds: float = Field(default=15.0, alias="INFERENCE_TIMEOUT_SECONDS")

    fir_inference_provider: str = Field(default="mock", alias="FIR_INFERENCE_PROVIDER")
    fir_inference_base_url: str = Field(default="http://localhost:8000/v1", alias="FIR_INFERENCE_BASE_URL")
    fir_inference_model_name: str = Field(default="", alias="FIR_INFERENCE_MODEL_NAME")
    fir_local_model_name: str = Field(default="", alias="FIR_LOCAL_MODEL_NAME")
    fir_max_generation_tokens: int = Field(default=900, alias="FIR_MAX_GENERATION_TOKENS")
    fir_temperature: float = Field(default=0.15, alias="FIR_TEMPERATURE")
    fir_inference_timeout_seconds: float = Field(default=10.0, alias="FIR_INFERENCE_TIMEOUT_SECONDS")

    upload_dir: Path = Field(default=Path("storage/uploads"), alias="UPLOAD_DIR")
    ocr_language: str = Field(default="eng+hin", alias="OCR_LANGUAGE")
    whisper_model: str = Field(default="tiny", alias="WHISPER_MODEL")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return normalize_turso_database_url(self.database_url)
        if self.turso_database_url:
            return normalize_turso_database_url(self.turso_database_url)
        return f"sqlite+pysqlite:///{self.app_sqlite_path.resolve().as_posix()}"

    @property
    def resolved_database_connect_args(self) -> dict:
        if self.resolved_database_url.startswith("sqlite+libsql://"):
            return {"auth_token": self.turso_auth_token} if self.turso_auth_token else {}
        if self.resolved_database_url.startswith("sqlite"):
            return {"check_same_thread": False}
        return {}

    @property
    def admin_email_allowlist(self) -> set[str]:
        return {
            email.strip().lower()
            for email in self.admin_emails.split(",")
            if email and email.strip()
        }


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.persistent_storage_root = (
        settings.persistent_storage_root if settings.persistent_storage_root and settings.persistent_storage_root.is_absolute()
        else resolve_repo_path(settings.persistent_storage_root) if settings.persistent_storage_root
        else None
    )
    settings.app_sqlite_path = resolve_storage_path(settings.app_sqlite_path, settings.persistent_storage_root)
    settings.analytics_db_path = resolve_storage_path(settings.analytics_db_path, settings.persistent_storage_root)
    settings.vector_index_path = resolve_storage_path(settings.vector_index_path, settings.persistent_storage_root)
    settings.vector_metadata_path = resolve_storage_path(settings.vector_metadata_path, settings.persistent_storage_root)
    settings.legal_corpus_path = resolve_repo_path(settings.legal_corpus_path)
    settings.bootstrap_corpus_path = resolve_repo_path(settings.bootstrap_corpus_path)
    settings.official_sources_manifest_path = resolve_repo_path(settings.official_sources_manifest_path)
    settings.jurisdiction_gazetteer_path = resolve_repo_path(settings.jurisdiction_gazetteer_path)
    settings.upload_dir = resolve_storage_path(settings.upload_dir, settings.persistent_storage_root)
    if settings.persistent_storage_root:
        settings.persistent_storage_root.mkdir(parents=True, exist_ok=True)
    settings.app_sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    settings.analytics_db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.vector_index_path.parent.mkdir(parents=True, exist_ok=True)
    settings.vector_metadata_path.parent.mkdir(parents=True, exist_ok=True)
    settings.page_index_path = resolve_storage_path(settings.page_index_path, settings.persistent_storage_root)
    settings.page_index_path.parent.mkdir(parents=True, exist_ok=True)
    settings.legal_corpus_path.parent.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings
