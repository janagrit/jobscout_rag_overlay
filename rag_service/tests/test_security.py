import pytest
from fastapi.testclient import TestClient

import app.main as main
from tests.conftest import TEST_TOKEN

INDEX = ("/internal/v1/profiles/index", {"tenant_id": "user-a", "profile_id": "cv-1", "profile_text": "Python QA engineer"})
EXPLAIN = (
    "/internal/v1/matches/explain",
    {
        "tenant_id": "user-a",
        "profile_id": "cv-1",
        "job": {"job_id": "j1", "title": "QA", "company": "Co", "description": "Playwright tests"},
    },
)
ROUTES = [INDEX, EXPLAIN]


@pytest.fixture
def anon(monkeypatch, service):
    monkeypatch.setattr("app.config.RAG_SERVICE_TOKEN", TEST_TOKEN)
    monkeypatch.setattr(main, "service_instance", service)
    return TestClient(main.app, raise_server_exceptions=False)


@pytest.mark.parametrize("path,body", ROUTES)
def test_missing_token_rejected(anon, path, body):
    assert anon.post(path, json=body).status_code == 401


@pytest.mark.parametrize("path,body", ROUTES)
@pytest.mark.parametrize("token", ["wrong", TEST_TOKEN + "x", TEST_TOKEN[:-1], " " + TEST_TOKEN])
def test_wrong_token_rejected(anon, path, body, token):
    resp = anon.post(path, json=body, headers={"X-Job-Scout-Service-Token": token})
    assert resp.status_code == 401


@pytest.mark.parametrize("path,body", ROUTES)
def test_correct_token_accepted(anon, path, body):
    resp = anon.post(path, json=body, headers={"X-Job-Scout-Service-Token": TEST_TOKEN})
    assert resp.status_code == 200


@pytest.mark.parametrize("path,body", ROUTES)
def test_unconfigured_server_token_rejects_everything(anon, monkeypatch, path, body):
    monkeypatch.setattr("app.config.RAG_SERVICE_TOKEN", "")
    assert anon.post(path, json=body, headers={"X-Job-Scout-Service-Token": ""}).status_code == 401
    assert anon.post(path, json=body).status_code == 401


def test_error_body_does_not_leak_token(anon):
    path, body = INDEX
    resp = anon.post(path, json=body, headers={"X-Job-Scout-Service-Token": "wrong"})
    assert TEST_TOKEN not in resp.text
    assert resp.json() == {"detail": "Unauthorized"}


def test_health_is_public_and_minimal(anon):
    resp = anon.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
