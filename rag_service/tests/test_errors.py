"""Upstream failures must become a generic 5xx without leaking details (contract: 5xx section)."""
import httpx2
import openai
import pytest

from tests.conftest import TEST_TOKEN, load_json

REQ = httpx2.Request("POST", "https://api.openai.com/v1/responses")
SECRET_DETAIL = "sk-live-SECRET-in-exception-text"


def openai_errors():
    return [
        openai.APIConnectionError(message=SECRET_DETAIL, request=REQ),
        openai.RateLimitError(SECRET_DETAIL, response=httpx2.Response(429, request=REQ), body=None),
        openai.APITimeoutError(request=REQ),
    ]


@pytest.fixture
def explain_body():
    return {"tenant_id": "tenant-a", "profile_id": "cv-1", "job": load_json("job_good_match.json")}


def assert_safe(resp, cv_text=""):
    assert 500 <= resp.status_code < 600
    assert resp.json() == {"detail": "Upstream error"}
    assert SECRET_DETAIL not in resp.text and TEST_TOKEN not in resp.text
    if cv_text:
        assert cv_text[:40] not in resp.text


@pytest.mark.parametrize("error", openai_errors(), ids=lambda e: type(e).__name__)
def test_chat_model_failure(api, service, fake_openai, cv_text, explain_body, error):
    service.index_profile("tenant-a", "cv-1", cv_text)
    fake_openai.response_error = error
    assert_safe(api.post("/internal/v1/matches/explain", json=explain_body), cv_text)


@pytest.mark.parametrize("error", openai_errors(), ids=lambda e: type(e).__name__)
def test_embedding_failure_on_index(api, fake_openai, cv_text, error):
    fake_openai.embed_error = error
    resp = api.post("/internal/v1/profiles/index",
                    json={"tenant_id": "tenant-a", "profile_id": "cv-1", "profile_text": cv_text})
    assert_safe(resp, cv_text)


def test_vector_store_failure(api, service, monkeypatch, explain_body):
    def boom(*args, **kwargs):
        raise RuntimeError(f"chroma exploded: {SECRET_DETAIL}")

    monkeypatch.setattr(service.store, "retrieve", boom)
    assert_safe(api.post("/internal/v1/matches/explain", json=explain_body))


def test_store_value_error_is_not_echoed_as_400(api, service, monkeypatch, cv_text):
    # Only the "empty profile" case is a client error; other ValueErrors are upstream failures.
    def bad(*args, **kwargs):
        raise ValueError(f"chroma invalid argument {SECRET_DETAIL}")

    monkeypatch.setattr(service.store, "index_profile", bad)
    resp = api.post("/internal/v1/profiles/index",
                    json={"tenant_id": "tenant-a", "profile_id": "cv-1", "profile_text": cv_text})
    assert_safe(resp, cv_text)


def test_upstream_error_has_correlation_id(api, service, fake_openai, cv_text, explain_body):
    service.index_profile("tenant-a", "cv-1", cv_text)
    fake_openai.response_error = openai_errors()[0]
    resp = api.post("/internal/v1/matches/explain", json=explain_body)
    assert len(resp.headers["X-Correlation-ID"]) == 32
