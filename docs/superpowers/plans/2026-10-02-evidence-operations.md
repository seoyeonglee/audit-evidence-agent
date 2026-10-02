# Evidence Operations Implementation Plan

> Execution: implement inline with test-first development and a final review pass.

**Goal:** Persist and secure the evidence workflow, demonstrate its operation, and publish reproducible measurements.

**Architecture:** Existing FastAPI/React application plus a bounded operations module. SQL-backed queue and canonical records share transactions. PostgreSQL RLS adds isolation; SQLite is the local demo backend.

**Tech Stack:** Python, FastAPI, SQLAlchemy, PostgreSQL, SQLite, React, TypeScript, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-02-evidence-operations-design.md`

## Global constraints
- Synthetic data only; measurements must name their workload and provider.
- Preserve existing v1 RAG routes and UI; new workflow lives under `/api/v2`.
- No paid infrastructure, fabricated history, or unexecuted success claims.

## Review focus
- Concurrent duplicate submissions return one job, not two.
- Expired worker leases cannot overwrite a newer worker's output.
- Request owner cannot approve their own evidence or widen their scope through headers.
- An additional document cannot change an approved record.
- Missing/malformed fields and prompt-like instructions must not become approved facts.

### Task 1: Persisted workflow and authorization
Files: `src/platform/{models,database,auth,service}.py`, `tests/platform/test_workflow.py`.
Interfaces: `Store(url)`, `seed_demo(store)`, `EvidenceService(store)`, `Principal`, `submit(principal, request_id, key, document)`, `review(principal, request_id, version, decision, feedback)`.
- [ ] Write tests for isolation, role scope, idempotency, stale review and immutable approval; observe failures.
- [ ] Implement persisted records, source documents, jobs and audit events with transactional mutations.
- [ ] Run the existing and new suites; commit the functioning domain.

### Task 2: Processing and database boundary
Files: `src/platform/{extraction,worker,routes}.py`, `infrastructure/postgres/*.sql`, `tests/platform/{test_worker,test_api,test_postgres}.py`.
Interfaces: `extract(document) -> Extraction`, `Worker.tick() -> bool`, `create_router(store) -> APIRouter`.
- [ ] Write tests for source attribution, malformed inputs, retries, dead letters, lease recovery and direct SQL tenant violations; observe failures.
- [ ] Implement extraction, leased jobs, authenticated v2 routes and PostgreSQL policies/triggers.
- [ ] Run SQLite/API and PostgreSQL integration suites; commit.

### Task 3: Operations interface and measured results
Files: `frontend/src/operations/*`, `scripts/{evaluate_platform,benchmark,capture}.py`, `docs/reports/*`, `tests/e2e/*`.
Interfaces: persona session and typed `/api/v2` requests; scripts emit versioned JSON reports.
- [ ] Write browser assertions for submission, processing, restricted persona and approval.
- [ ] Implement operations dashboard with lineage, durable reviews, job states and event history.
- [ ] Run browser workflow, typecheck/build, evaluation and benchmark; capture actual screenshots/results.
- [ ] Commit interface and reports.

### Task 4: Engineering evidence and delivery
Files: README, ADRs, runbooks, threat model, playbook, CI, Docker deployment.
- [ ] Document decisions, limits, operating procedures and reusable domain mapping.
- [ ] Add CI running backend/frontend, PostgreSQL security tests and browser flow with report artifacts.
- [ ] Review diff; rerun required checks; publish changes to GitHub and verify remote commit/CI.
