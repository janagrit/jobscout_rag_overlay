# Job Scout RAG service (initial integration slice)

This is an internal Python service scaffold for the first RAG feature: evidence-based job-match explanations.

## Local setup

```bash
cd rag_service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set OPENAI_API_KEY and a long random RAG_SERVICE_TOKEN in .env
uvicorn app.main:app --reload --port 8001
```

Health check: `GET http://localhost:8001/health`

Run unit/security tests:

```bash
pytest -q
```

## Internal API

All `/internal/*` routes require `X-Job-Scout-Service-Token`. The Cloudflare Worker must authenticate the user first and derive `tenant_id` from its verified session. Never accept a browser-supplied tenant/user ID as authority.

1. `POST /internal/v1/profiles/index` — index one candidate profile.
2. `POST /internal/v1/matches/explain` — retrieve profile evidence relevant to a job and generate a grounded explanation.

The service is not intended to be exposed directly to browsers. Put it behind TLS and network restrictions. Do not log profile text, job descriptions, prompts, or model responses.

## Important production hardening

The initial vector store uses a separate Chroma collection name derived from tenant + profile IDs and checks tenant metadata on retrieval. This is an MVP isolation measure, not a substitute for production database-level row-level security. Before production, use a vector store with enforceable tenant isolation (for example PostgreSQL + pgvector with RLS), add rate limits, request IDs, audit events without sensitive content, retention/deletion hooks, and key rotation.
