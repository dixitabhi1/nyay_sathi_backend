from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.fir_service import FIRService


def _service() -> FIRService:
    service = object.__new__(FIRService)
    service.settings = SimpleNamespace(admin_email_allowlist=set())
    return service


def test_fir_intake_falls_back_to_citizen_track_for_public_viewer():
    service = _service()

    assert service._intake_document_kind_for_viewer("police_fir", None) == "citizen_application"
    assert service._intake_document_kind_for_viewer("lawyer_analysis", None) == "citizen_application"


def test_fir_intake_preserves_approved_role_track():
    service = _service()
    police_viewer = SimpleNamespace(email="police@example.com", role="police", approval_status="approved")
    lawyer_viewer = SimpleNamespace(email="lawyer@example.com", role="lawyer", approval_status="approved")

    assert service._intake_document_kind_for_viewer("police_fir", police_viewer) == "police_fir"
    assert service._intake_document_kind_for_viewer("lawyer_analysis", lawyer_viewer) == "lawyer_analysis"


def test_strict_fir_document_access_still_blocks_protected_tracks():
    service = _service()

    with pytest.raises(HTTPException) as exc_info:
        service._ensure_document_kind_access("police_fir", None)

    assert exc_info.value.status_code == 403
