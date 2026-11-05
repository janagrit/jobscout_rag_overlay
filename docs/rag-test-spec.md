# Job Scout RAG: integration test specification

These tests belong in the **main Job Scout repo** (`worker/`, `web/`, Playwright `tests/`). The `rag_service` side is already covered by `rag_service/tests` (offline pytest suite) and `rag_service/tests/evals` (opt-in live model checks).

## Shared contract fixtures

`docs/contract-fixtures/*.json` contain request/expected-status cases for each RAG endpoint. `rag_service/tests/test_api_contract.py` already runs them against the service. Worker tests should load the same files to build mocked RAG responses, so the two sides cannot drift apart. When the contract changes, update the fixtures first.

Placeholders such as `PROFILE_OVER_LIMIT` and `SKILLS_101` are expanded by the test code (see `PLACEHOLDERS` in `test_api_contract.py`).

## Worker route tests

Use the repo's existing Worker test setup. If there is none, use `@cloudflare/vitest-pool-workers` with a D1 binding and a mocked `fetch` to `RAG_SERVICE_URL`.

| # | Scenario | Expected |
|---|---|---|
| W1 | No session | 401; RAG `fetch` never called |
| W2 | User A explains a job; request body also contains `tenant_id: "B"` / `user_id: "B"` | RAG request has `tenant_id = currentUser().id` (A); body IDs ignored |
| W3 | User A requests while user B also has a CV in D1 | Only A's `files` row (`user_id = A`, `path = profile/cv.*`) is read |
| W4 | User has no CV | Clear "upload your CV" error (e.g. 409/404); RAG never called |
| W5 | CV > 100,000 chars or description > 30,000 chars | 413 before any RAG call |
| W6 | RAG does not respond within the timeout (e.g. 15s `AbortController`) | 504, generic message |
| W7 | RAG returns 401 / 500 / 502 | Worker returns a generic 502; log contains only a correlation ID (pass through RAG's `X-Correlation-ID`), never the token, CV text or response body |
| W8 | Any RAG call | Has `X-Job-Scout-Service-Token` from the Worker secret, uses HTTPS |
| W9 | CV content changes | New `profile_id` (content hash) and re-index before explain; unchanged CV does not re-index |
| W10 | RAG returns 200 | Worker forwards only `explanation`, `strengths`, `gaps`, `evidence`, `disclaimer` |

## Playwright UI tests: "Explain match" on the job card

Mock the Worker endpoint with `page.route` so the tests are deterministic and need no model.

| # | Scenario | Expected |
|---|---|---|
| P1 | Click "Explain match" while the request is still pending | Loading indicator; button disabled |
| P2 | Success | Explanation, strengths and gaps shown; evidence shown as quotes labelled `CV-n` |
| P3 | Success | Disclaimer visible |
| P4 | Worker says "no CV" | Empty state with a link to upload a CV |
| P5 | Worker returns 5xx or times out | Generic error message and a Retry button that works |
| P6 | Double-click | Exactly one request sent |
| P7 | Logged out | Button hidden, or the click redirects to login |
| P8 | Explanation contains `<img src=x onerror=alert(1)>` | Rendered as text; no dialog fires |
| P9 | Keyboard only | Button reachable with Tab and activated with Enter; the panel has an accessible name; focus moves to the result |

## Live-site smoke test (optional)

A separate Playwright project with `baseURL: https://job-scout-agent.com` and a dedicated test account that has credentials in CI secrets and a synthetic CV. It logs in, opens a job, clicks "Explain match", and expects at least one evidence item and the disclaimer. Run it manually or nightly, never on every PR, because it calls the real model.
