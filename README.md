# Job Scout RAG service

[![tests](https://github.com/janagrit/jobscout_rag_overlay/actions/workflows/tests.yml/badge.svg)](https://github.com/janagrit/jobscout_rag_overlay/actions/workflows/tests.yml)

A small Python service that powers **"Explain my match"** for [Job Scout](https://job-scout-agent.com). Given a candidate's CV and a job posting, it finds the CV passages most relevant to the job and asks an LLM to explain the match. The explanation lists strengths and gaps, and **every claim is backed by a quote from the CV**.

It is an add-on ("overlay") to the main Job Scout app. The browser never calls it directly; the app's Cloudflare Worker does.

```
Browser ──► Cloudflare Worker ──(service token, TLS)──► rag_service ──► OpenAI (embeddings + chat)
            authenticates user                          FastAPI           Chroma (vector store)
            loads the user's CV
```

## What it does

1. **Index a profile:** `POST /internal/v1/profiles/index`. The CV is split into overlapping chunks, embedded, and stored in a per-tenant Chroma collection.
2. **Explain a match:** `POST /internal/v1/matches/explain`. The service retrieves the top-k CV chunks for the job and sends them to the model as data together with the job. It returns:

```json
{
  "explanation": "The profile shows six years of Playwright and pytest automation…",
  "strengths": ["Built a ~400-test Playwright suite", "CI in GitHub Actions"],
  "gaps": ["No TypeScript evidence in the CV"],
  "evidence": [{"source_id": "CV-1", "excerpt": "Built a Playwright end-to-end suite…", "relevance_distance": 0.18}],
  "disclaimer": "This is an evidence-based assistant explanation, not a hiring prediction or guarantee."
}
```

### Safety built in
- **Tenant isolation:** each account's CV lives in its own collection, and every result is checked against the tenant ID.
- **Grounded evidence:** quotes or source IDs the model invents are dropped, so only real CV text is returned.
- **Prompt-injection resistant:** job descriptions and CVs are passed to the model as JSON data, never as instructions.
- **No leaks:** upstream failures return a generic `502` with a correlation ID. CVs, prompts and keys are never logged.
- **Internal only:** every `/internal/*` route requires the `X-Job-Scout-Service-Token` header.

## Tests

| Suite | What it covers | Runs |
|---|---|---|
| `rag_service/tests` (offline suite; coverage must stay ≥ 90%) | API contract and status codes, auth, tenant isolation, chunking, grounding of model evidence, prompt injection, error handling. Uses a fake OpenAI client and in-memory Chroma. | Every push (CI badge above). No API key needed. |
| `rag_service/tests/evals` | Real-model quality checks: cited quotes are verbatim CV text, no invented skills, injection is ignored, age or nationality is not used. | Manual: `pytest -m live` |
| `docs/rag-test-spec.md` | Worker and Playwright test specs for the main Job Scout app | In the main repo |

Every run ends with a **Test results** table: tests per file, totals and `app/` coverage. In CI the same table is on each run's summary page under [Actions](https://github.com/janagrit/jobscout_rag_overlay/actions/workflows/tests.yml).

## Quick start

```bash
cd rag_service
python3.12 -m venv .venv && source .venv/bin/activate   # Python 3.10+
pip install -r requirements.txt
cp .env.example .env          # set OPENAI_API_KEY and RAG_SERVICE_TOKEN
pytest -q                     # offline tests
uvicorn app.main:app --port 8001
```

See [`rag_service/README.md`](rag_service/README.md) for configuration and [`docs/rag-api-contract.md`](docs/rag-api-contract.md) for the full API.

## Status

MVP. Before production it still needs a vector store with database-enforced tenant isolation (for example pgvector with row-level security), rate limiting, and vector deletion when a CV is replaced or an account is deleted. See [`docs/rag-integration-plan.md`](docs/rag-integration-plan.md).

## License

Proprietary. All rights reserved. See [LICENSE](LICENSE).
