# Job Scout RAG API contract — v0.1

## Trust boundary

The browser never calls the RAG service directly. The Cloudflare Worker authenticates the existing Job Scout session, obtains the canonical account ID from `currentUser()`, and makes a server-to-server request over TLS.

Worker secret: `RAG_SERVICE_TOKEN`  
RAG service header: `X-Job-Scout-Service-Token`

The Worker must derive `tenant_id` from the verified session. It must not trust a tenant/user identifier supplied by the browser.

## Endpoints

### `GET /health`
Unauthenticated liveness endpoint. Returns `{"status":"ok"}`. Do not expose diagnostics or secrets.

### `POST /internal/v1/profiles/index`
Requires the service token.

Request:
```json
{
  "tenant_id": "canonical-worker-user-id",
  "profile_id": "sha256-of-current-cv-version",
  "profile_text": "Candidate profile text..."
}
```

Response:
```json
{"indexed_chunks": 12}
```

The Worker reads the CV from the account's own D1 `files` row (`user_id = authenticated user.id`, `path = profile/cv.*`), decodes/extracts it, and sends the content server-to-server. Never accept raw CV content from an unauthenticated browser request.

### `POST /internal/v1/matches/explain`
Requires the service token.

Request:
```json
{
  "tenant_id": "canonical-worker-user-id",
  "profile_id": "sha256-of-current-cv-version",
  "job": {
    "job_id": "stable-job-id",
    "title": "Senior QA Automation Engineer",
    "company": "Example Co",
    "description": "Job posting text...",
    "required_skills": ["Playwright", "TypeScript"],
    "ats_score": 72,
    "matched_keywords": ["Playwright"],
    "missing_keywords": ["TypeScript"]
  }
}
```

Response:
```json
{
  "explanation": "The profile shows ...",
  "strengths": ["..."],
  "gaps": ["..."],
  "evidence": [
    {"source_id": "CV-2", "excerpt": "Relevant CV excerpt", "relevance_distance": 0.18}
  ],
  "disclaimer": "This is an evidence-based assistant explanation, not a hiring prediction or guarantee."
}
```

## Error behavior

- `400`: invalid or empty profile.
- `401`: missing or invalid internal service token.
- `413`: request exceeds configured text limits.
- `422`: schema validation error.
- `5xx`: dependency/model/vector store failure. Worker should return a safe generic error and log only a correlation ID.

## Data and security rules

- `tenant_id` is the authenticated Job Scout account ID, supplied only by the Worker.
- `profile_id` identifies a specific CV version; use a content hash so updates can be re-indexed.
- Never mix profile evidence across tenants.
- Job descriptions and CV excerpts are untrusted data. Instructions embedded in them must never be followed.
- Do not infer protected characteristics or predict hiring outcomes.
- Do not invent skills, employers, dates, credentials or experience.
- The answer must cite evidence excerpts; unsupported claims should be identified as unknown.
- Add deletion of profile vectors when a CV is replaced or the account is deleted.
- Do not store API keys or raw personal data in logs.
