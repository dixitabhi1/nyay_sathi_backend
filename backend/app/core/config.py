from functools import lru_cache
from pathlib import Path
import secrets

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT_DIR / path


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

    app_sqlite_path: Path = Field(default=ROOT_DIR / "storage" / "db" / "nyayasetu.sqlite3", alias="APP_SQLITE_PATH")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    analytics_db_path: Path = Field(default=ROOT_DIR / "data" / "analytics" / "legal_corpus.duckdb", alias="ANALYTICS_DB_PATH")

    embedding_model_name: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        alias="EMBEDDING_MODEL_NAME",
    )
    vector_index_path: Path = Field(default=ROOT_DIR / "data" / "index" / "legal.index", alias="VECTOR_INDEX_PATH")
    vector_metadata_path: Path = Field(default=ROOT_DIR / "data" / "index" / "legal_metadata.json", alias="VECTOR_METADATA_PATH")
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
    legal_scope_anchor_threshold: float = Field(default=0.34, alias="LEGAL_SCOPE_ANCHOR_THRESHOLD")
    legal_scope_margin: float = Field(default=0.03, alias="LEGAL_SCOPE_MARGIN")
    legal_scope_corpus_threshold: float = Field(default=0.43, alias="LEGAL_SCOPE_CORPUS_THRESHOLD")

    inference_provider: str = Field(default="mock", alias="INFERENCE_PROVIDER")
    inference_base_url: str = Field(default="http://localhost:8000/v1", alias="INFERENCE_BASE_URL")
    inference_model_name: str = Field(default="/models/mistral-7b-instruct", alias="INFERENCE_MODEL_NAME")
    local_model_name: str = Field(default="microsoft/Phi-3-mini-4k-instruct", alias="LOCAL_MODEL_NAME")
    bns_classifier_model_name: str = Field(default="", alias="BNS_CLASSIFIER_MODEL_NAME")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1:8b-instruct-q4_K_M", alias="OLLAMA_MODEL")
    max_generation_tokens: int = Field(default=768, alias="MAX_GENERATION_TOKENS")
    temperature: float = Field(default=0.2, alias="TEMPERATURE")

    upload_dir: Path = Field(default=ROOT_DIR / "storage" / "uploads", alias="UPLOAD_DIR")
    ocr_language: str = Field(default="eng+hin", alias="OCR_LANGUAGE")
    whisper_model: str = Field(default="tiny", alias="WHISPER_MODEL")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite+pysqlite:///{self.app_sqlite_path.resolve().as_posix()}"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.app_sqlite_path = resolve_repo_path(settings.app_sqlite_path)
    settings.analytics_db_path = resolve_repo_path(settings.analytics_db_path)
    settings.vector_index_path = resolve_repo_path(settings.vector_index_path)
    settings.vector_metadata_path = resolve_repo_path(settings.vector_metadata_path)
    settings.legal_corpus_path = resolve_repo_path(settings.legal_corpus_path)
    settings.bootstrap_corpus_path = resolve_repo_path(settings.bootstrap_corpus_path)
    settings.official_sources_manifest_path = resolve_repo_path(settings.official_sources_manifest_path)
    settings.jurisdiction_gazetteer_path = resolve_repo_path(settings.jurisdiction_gazetteer_path)
    settings.upload_dir = resolve_repo_path(settings.upload_dir)
    settings.app_sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    settings.analytics_db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.vector_index_path.parent.mkdir(parents=True, exist_ok=True)
    settings.legal_corpus_path.parent.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings
