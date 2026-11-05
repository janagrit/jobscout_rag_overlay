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
        return {
            "explanation": str(parsed.get("explanation", "")),
            "strengths": parsed.get("strengths", []) if isinstance(parsed.get("strengths"), list) else [],
            "gaps": parsed.get("gaps", []) if isinstance(parsed.get("gaps"), list) else [],
            "evidence": parsed.get("evidence", []) if isinstance(parsed.get("evidence"), list) else [],
        }
