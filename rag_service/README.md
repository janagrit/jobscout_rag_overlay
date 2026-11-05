# Job Scout RAG service (initial integration slice)

This is an internal Python service scaffold for the first RAG feature: evidence-based job-match explanations.

## Requirements

Python **3.10 or newer** (the code uses `X | None` type syntax). macOS ships Python 3.9 as `python3`, so use a newer interpreter explicitly, e.g. Homebrew's `python3.12`.

## Local setup

```bash
cd rag_service
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set OPENAI_API_KEY and a long random RAG_SERVICE_TOKEN in .env
# Generate a token: python -c "import secrets; print(secrets.token_urlsafe(48))"
uvicorn app.main:app --reload --port 8001
```

## Configuration

Settings are read from environment variables. `app/config.py` also loads `rag_service/.env` automatically (from any working directory). Real environment variables take precedence over `.env`. `.env` is git-ignored — never commit it; keep `.env.example` in sync when adding settings.

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | — (required) | OpenAI API key |
| `OPENAI_CHAT_MODEL` | `gpt-4.1-mini` | Model for match explanations |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `RAG_SERVICE_TOKEN` | — (required) | Shared secret for `X-Job-Scout-Service-Token` |
| `CHROMA_PATH` | `./chroma_db` | Local Chroma storage directory |
| `TOP_K` | `5` | Number of profile chunks retrieved per job |

Health check: `GET http://localhost:8001/health`

## Testing

```bash
pytest -q                                    # offline suite: no network, no OpenAI key, no files written
pytest -q --cov=app --cov-report=term-missing
pytest -m live -q -s                         # live model quality checks (needs a real OPENAI_API_KEY; costs money)
```

- `tests/conftest.py` provides a deterministic `FakeOpenAI` and an in-memory Chroma store. Use the `api`, `service` and `store` fixtures in new tests.
- `tests/test_api_contract.py` runs the shared cases in `../docs/contract-fixtures/`. The Worker tests in the main repo use the same files.
- `tests/evals/` holds grounding, injection and fairness checks against the real model. They are marked `live` and excluded by default.
- Integration tests for the Worker and UI are specified in `../docs/rag-test-spec.md`.

## Internal API

All `/internal/*` routes require `X-Job-Scout-Service-Token`. The Cloudflare Worker must authenticate the user first and derive `tenant_id` from its verified session. Never accept a browser-supplied tenant/user ID as authority.

1. `POST /internal/v1/profiles/index` — index one candidate profile.
2. `POST /internal/v1/matches/explain` — retrieve profile evidence relevant to a job and generate a grounded explanation.

The service is not intended to be exposed directly to browsers. Put it behind TLS and network restrictions. Do not log profile text, job descriptions, prompts, or model responses.

## Important production hardening

The initial vector store uses a separate Chroma collection name derived from tenant + profile IDs and checks tenant metadata on retrieval. This is an MVP isolation measure, not a substitute for production database-level row-level security. Before production, use a vector store with enforceable tenant isolation (for example PostgreSQL + pgvector with RLS), add rate limits, request IDs, audit events without sensitive content, retention/deletion hooks, and key rotation.
