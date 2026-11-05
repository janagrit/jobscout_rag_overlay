# Job Scout RAG integration plan

## Repository facts confirmed from the supplied archive

- Frontend: React + Vite (`web/`).
- Site backend: Cloudflare Worker (`worker/`).
- Account data: Cloudflare D1 (`migrations/0001_init.sql`).
- Existing user authentication: `currentUser()` in `worker/auth.ts`.
- Per-user CV storage: `files` table keyed by `(user_id, path)`; CV paths are allow-listed in `worker/index.ts`.
- Existing job matching: `src/match.ts`.
- Existing AI tailoring: `src/ai.ts` and `src/tailor-prompt.ts`.
- Existing browser test suite: Playwright (`tests/`).

## First feature

"Explain my match" on a job card.

Inputs come from existing trusted application data:
- Canonical user ID from the Worker session.
- CV text read from that user's own D1 file record.
- Job title, company, description and required skills from the selected job record.
- Existing ATS score and matched/missing keyword signals, if available.

The Python service retrieves CV passages relevant to the selected job and produces a concise explanation with evidence, strengths and gaps.

## Proposed change sequence

1. Keep the current TypeScript/Cloudflare architecture unchanged.
2. Add the Python service as a separate deployable component under `rag_service/`.
3. Add Worker secrets/configuration for `RAG_SERVICE_URL` and `RAG_SERVICE_TOKEN`.
4. Add an authenticated Worker route. The route must call `currentUser()` first, derive the tenant ID from that result, and load the CV server-side from D1.
5. Add a frontend "Explain match" action to the existing job card; the browser sends only the job identifier and necessary display context, never a trusted user ID.
6. Add Worker tests for unauthenticated access, cross-account CV access, missing CV, oversized payload, RAG timeout and upstream error.
7. Add Playwright coverage for loading, empty state, evidence citations and error handling.
8. Add evaluation fixtures with expected evidence and adversarial job descriptions.
9. Deploy the Python service behind TLS and restrict it to Worker-to-service traffic.

## Baseline test status

The supplied archive includes a broad Playwright suite and TypeScript typecheck script. A dependency installation was attempted in this environment but did not complete before timeout. The subsequent `npm run typecheck` could not start because the partial installation lacked `@types/node`. Therefore no baseline test result is claimed. Re-run `npm ci`, `npm run typecheck`, and `npm test` in a complete local checkout before integration.
