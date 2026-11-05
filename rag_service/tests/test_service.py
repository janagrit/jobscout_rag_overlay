import json

import pytest

from app.prompts import SYSTEM_PROMPT
from tests.conftest import load_json


@pytest.fixture
def job():
    return load_json("job_good_match.json")


@pytest.fixture
def indexed(service, cv_text):
    service.index_profile("tenant-a", "cv-1", cv_text)
    return service


def retrieved_ids(service, job):
    query = " ".join([job["title"], job["description"], *job["required_skills"]])
    return {e["source_id"]: e for e in service.store.retrieve("tenant-a", "cv-1", query, service.embed, 5)}


def test_no_profile_skips_model_call(service, fake_openai, job):
    result = service.explain_match("tenant-a", "cv-1", job)
    assert result["evidence"] == []
    assert "No candidate profile evidence" in result["explanation"]
    assert fake_openai.response_calls == []


def test_prompt_structure_keeps_job_as_data(indexed, fake_openai, job):
    indexed.explain_match("tenant-a", "cv-1", job)
    (call,) = fake_openai.response_calls
    assert call["instructions"] == SYSTEM_PROMPT
    assert job["description"] not in call["instructions"]
    payload = json.loads(call["input"])
    assert payload["job"]["description"] == job["description"]
    assert payload["candidate_profile_evidence"], "retrieved evidence must be sent to the model"
    # job_id is not needed by the model and must not be forwarded.
    assert "job_id" not in payload["job"]


def test_embedding_model_from_config(indexed, fake_openai, job):
    from app.config import OPENAI_EMBEDDING_MODEL
    assert {c["model"] for c in fake_openai.embedding_calls} == {OPENAI_EMBEDDING_MODEL}


def test_non_json_model_output_falls_back(indexed, fake_openai, job):
    fake_openai.output_text = "Sorry, plain text answer."
    result = indexed.explain_match("tenant-a", "cv-1", job)
    assert result["explanation"] == "Sorry, plain text answer."
    assert result["strengths"] == [] and result["gaps"] == [] and result["evidence"] == []


def test_empty_model_output_falls_back(indexed, fake_openai, job):
    fake_openai.output_text = ""
    result = indexed.explain_match("tenant-a", "cv-1", job)
    assert result["explanation"] == "The model did not return a usable explanation."


@pytest.mark.parametrize("strengths,gaps", [("a string", None), ({"k": 1}, 42)])
def test_wrong_field_types_become_empty_lists(indexed, fake_openai, job, strengths, gaps):
    fake_openai.output_text = json.dumps(
        {"explanation": "x", "strengths": strengths, "gaps": gaps, "evidence": "nope"}
    )
    result = indexed.explain_match("tenant-a", "cv-1", job)
    assert result["strengths"] == [] and result["gaps"] == [] and result["evidence"] == []


def test_list_items_are_coerced_to_strings(indexed, fake_openai, job):
    fake_openai.output_text = json.dumps(
        {"explanation": "x", "strengths": ["Playwright", 6, None], "gaps": [{"skill": "TS"}], "evidence": []}
    )
    result = indexed.explain_match("tenant-a", "cv-1", job)
    assert all(isinstance(s, str) for s in result["strengths"] + result["gaps"])
    assert "Playwright" in result["strengths"] and "6" in result["strengths"]
    assert None not in result["strengths"]


def test_invented_evidence_is_dropped(indexed, fake_openai, job):
    real = retrieved_ids(indexed, job)
    real_id = next(iter(real))
    fake_openai.output_text = json.dumps({
        "explanation": "x", "strengths": [], "gaps": [],
        "evidence": [
            {"source_id": "CV-99", "excerpt": "10 years of Kubernetes"},
            {"excerpt": "no source id at all"},
            "just a string",
            {"source_id": real_id, "excerpt": "an edited quote the CV never said"},
        ],
    })
    result = indexed.explain_match("tenant-a", "cv-1", job)
    assert [e["source_id"] for e in result["evidence"]] == [real_id]
    # The excerpt must be the retrieved CV text, not the model's paraphrase.
    assert result["evidence"][0]["excerpt"] == real[real_id]["excerpt"]


def test_duplicate_evidence_is_deduplicated(indexed, fake_openai, job):
    real_id = next(iter(retrieved_ids(indexed, job)))
    fake_openai.output_text = json.dumps({
        "explanation": "x", "strengths": [], "gaps": [],
        "evidence": [{"source_id": real_id, "excerpt": "a"}, {"source_id": real_id, "excerpt": "b"}],
    })
    result = indexed.explain_match("tenant-a", "cv-1", job)
    assert len(result["evidence"]) == 1
