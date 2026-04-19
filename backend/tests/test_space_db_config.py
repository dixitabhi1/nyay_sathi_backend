from app.core.config import get_space_local_app_db_fallback_reason


def test_space_local_app_db_fallback_reason_prefers_local_db():
    reason = get_space_local_app_db_fallback_reason(
        is_huggingface_space=True,
        resolved_database_url="sqlite+libsql://example.turso.io?secure=true",
        prefer_local_app_db_on_space=True,
        allow_remote_app_db_on_space=True,
    )

    assert reason == "local app DB preference enabled"


def test_space_local_app_db_fallback_reason_blocks_remote_db_when_disabled():
    reason = get_space_local_app_db_fallback_reason(
        is_huggingface_space=True,
        resolved_database_url="sqlite+libsql://example.turso.io?secure=true",
        prefer_local_app_db_on_space=False,
        allow_remote_app_db_on_space=False,
    )

    assert reason == "remote app DB on Space is disabled"


def test_space_local_app_db_fallback_reason_allows_remote_db_when_enabled():
    reason = get_space_local_app_db_fallback_reason(
        is_huggingface_space=True,
        resolved_database_url="sqlite+libsql://example.turso.io?secure=true",
        prefer_local_app_db_on_space=False,
        allow_remote_app_db_on_space=True,
    )

    assert reason is None
