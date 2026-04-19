from app.services.auth import get_missing_user_login_detail


def test_missing_user_login_detail_is_generic_when_remote_db_is_active():
    detail = get_missing_user_login_detail(
        is_huggingface_space=False,
        resolved_database_url="sqlite+libsql://example.turso.io?secure=true",
        engine_drivername="sqlite+libsql",
        space_local_app_db_fallback_reason=None,
    )

    assert detail == "Invalid email or password."


def test_missing_user_login_detail_explains_space_local_db_mode():
    detail = get_missing_user_login_detail(
        is_huggingface_space=True,
        resolved_database_url="sqlite+libsql://example.turso.io?secure=true",
        engine_drivername="sqlite+pysqlite",
        space_local_app_db_fallback_reason="local app DB preference enabled",
    )

    assert "local auth database" in detail
    assert "register again or migrate users" in detail


def test_missing_user_login_detail_explains_remote_db_outage():
    detail = get_missing_user_login_detail(
        is_huggingface_space=False,
        resolved_database_url="sqlite+libsql://example.turso.io?secure=true",
        engine_drivername="sqlite+pysqlite",
        space_local_app_db_fallback_reason=None,
    )

    assert "fallback local database" in detail
    assert "primary database" in detail
