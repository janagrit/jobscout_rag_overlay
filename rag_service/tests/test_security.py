from fastapi.testclient import TestClient
from app.main import app


def test_internal_endpoint_rejects_missing_service_token(monkeypatch):
    monkeypatch.setattr("app.config.RAG_SERVICE_TOKEN", "test-secret")
    client = TestClient(app)
    response = client.post("/internal/v1/profiles/index", json={
        "tenant_id": "user-a", "profile_id": "cv-1", "profile_text": "Python QA engineer"
    })
    assert response.status_code == 401


def test_internal_endpoint_rejects_wrong_service_token(monkeypatch):
    monkeypatch.setattr("app.config.RAG_SERVICE_TOKEN", "test-secret")
    client = TestClient(app)
    response = client.post(
        "/internal/v1/profiles/index",
        headers={"X-Job-Scout-Service-Token": "wrong"},
        json={"tenant_id": "user-a", "profile_id": "cv-1", "profile_text": "Python QA engineer"},
    )
    assert response.status_code == 401
