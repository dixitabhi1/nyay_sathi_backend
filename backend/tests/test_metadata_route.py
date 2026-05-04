from fastapi.testclient import TestClient

from app.main import app


def test_legal_metadata_file_is_visible():
    response = TestClient(app).get("/api/v1/metadata/legal-metadata.json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert isinstance(response.json(), list)


def test_legal_metadata_summary_returns_count_and_sample():
    response = TestClient(app).get("/api/v1/metadata/legal-metadata/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["record_count"] > 0
    assert isinstance(payload["sample"], list)
