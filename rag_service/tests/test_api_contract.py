"""Status codes and response shapes from docs/rag-api-contract.md, driven by docs/contract-fixtures."""
import copy
import json
from pathlib import Path

import pytest

from app.config import MAX_JOB_DESCRIPTION_CHARS, MAX_PROFILE_CHARS
from app.schemas import MatchExplainResponse

CONTRACT_DIR = Path(__file__).resolve().parents[2] / "docs" / "contract-fixtures"
INDEX = json.loads((CONTRACT_DIR / "index-profile.json").read_text())
EXPLAIN = json.loads((CONTRACT_DIR / "explain-match.json").read_text())

PLACEHOLDERS = {
    "TENANT_129_CHARS": "t" * 129,
    "PROFILE_OVER_LIMIT": "a" * (MAX_PROFILE_CHARS + 1),
    "DESCRIPTION_OVER_LIMIT": "d" * (MAX_JOB_DESCRIPTION_CHARS + 1),
    "SKILLS_101": [f"skill-{i}" for i in range(101)],
}


def expand(value):
    if isinstance(value, dict):
        return {k: expand(v) for k, v in value.items()}
    if isinstance(value, str) and value in PLACEHOLDERS:
        return PLACEHOLDERS[value]
    return value


@pytest.mark.parametrize("case", INDEX["cases"], ids=lambda c: c["name"])
def test_index_contract(api, case):
    resp = api.post("/internal/v1/profiles/index", json=expand(case["body"]))
    assert resp.status_code == case["status"], resp.text
    for key in case.get("response_keys", []):
        assert key in resp.json()


@pytest.mark.parametrize("case", EXPLAIN["cases"], ids=lambda c: c["name"])
def test_explain_contract(api, case):
    job = copy.deepcopy(EXPLAIN["base_job"])
    job.update(expand(case["job_overrides"]))
    body = {"tenant_id": "user-a", "profile_id": "sha256-abc", "job": job}
    resp = api.post("/internal/v1/matches/explain", json=body)
    assert resp.status_code == case["status"], resp.text[:300]
    if resp.status_code == 200:
        data = resp.json()
        for key in case["response_keys"]:
            assert key in data
        MatchExplainResponse.model_validate(data)
        assert data["disclaimer"] == EXPLAIN["disclaimer"]


def test_index_reports_chunk_count(api, cv_text):
    resp = api.post(
        "/internal/v1/profiles/index",
        json={"tenant_id": "user-a", "profile_id": "cv-1", "profile_text": cv_text},
    )
    assert resp.status_code == 200
    assert resp.json()["indexed_chunks"] == 2  # ~1.1k chars with 900/120 chunking


def test_profile_exactly_at_limit_is_accepted(api):
    resp = api.post(
        "/internal/v1/profiles/index",
        json={"tenant_id": "user-a", "profile_id": "cv-1", "profile_text": "a" * MAX_PROFILE_CHARS},
    )
    assert resp.status_code == 200
