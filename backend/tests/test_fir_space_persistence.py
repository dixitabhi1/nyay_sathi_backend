from types import SimpleNamespace

from app.services.fir_service import FIRService


def test_fir_persistence_is_non_blocking_for_space_remote_db():
    service = object.__new__(FIRService)
    service.settings = SimpleNamespace(
        is_huggingface_space=True,
        resolved_database_url="sqlite+libsql://example.turso.io?secure=true",
        space_local_app_db_fallback_reason=None,
    )

    assert service._should_skip_blocking_fir_persistence() is True


def test_fir_persistence_uses_local_db_when_space_fallback_is_enabled():
    service = object.__new__(FIRService)
    service.settings = SimpleNamespace(
        is_huggingface_space=True,
        resolved_database_url="sqlite+libsql://example.turso.io?secure=true",
        space_local_app_db_fallback_reason="local app DB preference enabled",
    )

    assert service._should_skip_blocking_fir_persistence() is False
