import json
from openai import OpenAI
from app.config import OPENAI_CHAT_MODEL, OPENAI_EMBEDDING_MODEL, TOP_K
from app.prompts import SYSTEM_PROMPT
from app.store import ProfileStore


class RAGService:
    def __init__(self, client=None, store=None):
        self.client = client or OpenAI()
        self.store = store or ProfileStore()

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = self.client.embeddings.create(model=OPENAI_EMBEDDING_MODEL, input=texts)
        return [item.embedding for item in result.data]

    def index_profile(self, tenant_id: str, profile_id: str, text: str) -> int:
        return self.store.index_profile(tenant_id, profile_id, text, self.embed)

    def explain_match(self, tenant_id: str, profile_id: str, job: dict) -> dict:
        query = " ".join([job["title"], job["description"], *job.get("required_skills", [])])
        evidence = self.store.retrieve(tenant_id, profile_id, query, self.embed, TOP_K)
        if not evidence:
            return {
                "explanation": "No candidate profile evidence has been indexed for this account.",
                "strengths": [],
                "gaps": ["Index the candidate profile before requesting an explanation."],
                "evidence": [],
            }

        # Treat job content as data, never as instructions. Keep only necessary fields.
        job_context = {
            "title": job["title"], "company": job["company"],
            "description": job["description"],
            "required_skills": job.get("required_skills", []),
            "existing_ats_score": job.get("ats_score"),
            "existing_matched_keywords": job.get("matched_keywords", []),
            "existing_missing_keywords": job.get("missing_keywords", []),
        }
        user_input = {
            "job": job_context,
            "candidate_profile_evidence": evidence,
            "instruction": "Explain the match based only on this evidence. Return JSON.",
        }
        response = self.client.responses.create(
            model=OPENAI_CHAT_MODEL,
            instructions=SYSTEM_PROMPT,
            input=json.dumps(user_input, ensure_ascii=False),
        )
        raw = response.output_text
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            parsed = {
                "explanation": raw or "The model did not return a usable explanation.",
                "strengths": [],
                "gaps": [],
                "evidence": [],
            }
        if not isinstance(parsed, dict):
            parsed = {"explanation": raw}
        return {
            "explanation": str(parsed.get("explanation", "")),
            "strengths": _string_list(parsed.get("strengths")),
            "gaps": _string_list(parsed.get("gaps")),
            "evidence": _grounded_evidence(parsed.get("evidence"), evidence),
        }


def _string_list(value) -> list[str]:
    """Keep model list output only if it is a list; drop nulls and stringify other items."""
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if item is None:
            continue
        if isinstance(item, (dict, list)):
            item = json.dumps(item, ensure_ascii=False)
        result.append(str(item))
    return result


def _grounded_evidence(cited, retrieved: list[dict]) -> list[dict]:
    """Return only evidence the model cited that was actually retrieved, with the retrieved text.

    The model may invent source IDs or paraphrase quotes; responses must contain real CV excerpts.
    """
    if not isinstance(cited, list):
        return []
    by_id = {item["source_id"]: item for item in retrieved}
    grounded, seen = [], set()
    for item in cited:
        source_id = item.get("source_id") if isinstance(item, dict) else None
        if source_id in by_id and source_id not in seen:
            seen.add(source_id)
            grounded.append(dict(by_id[source_id]))
    return grounded
