# Evidence Operations Platform design

## Outcome
Extend the existing audit-evidence project into a reviewable engineering reference: a working multi-party workflow, persisted canonical records, tenant isolation, durable processing, and reproducible evidence of correctness. Keep the existing React control room and offline RAG demonstration available. All examples are synthetic. No claim of employment history or production traffic is made.

## Architecture
Use the existing Python/FastAPI modular monolith and React/TypeScript client. Introduce `src/platform` as a separate bounded context behind `/api/v2`. PostgreSQL is the deployment database; SQLite supports the zero-service local demo. A database-backed queue keeps evidence submission and job insertion in one transaction, avoiding a dual-write problem. PostgreSQL workers claim jobs with `FOR UPDATE SKIP LOCKED`; SQLite uses atomic claims. Workers have expiring leases, capped attempts and terminal dead-letter state.

## Identity and access
Opaque API tokens resolve to persisted tenant membership; user-supplied tenant headers are never authoritative. Auditor and reviewer can read tenant records. A control owner can read and submit only assigned requests. Vendors have only explicitly assigned upload/read access. Only reviewers approve or reject, and self-approval is blocked. Demo sessions expose fixed fictional personas only when `DEMO_MODE=1`. Tenant filtering applies to records, jobs and events, with PostgreSQL FORCE RLS as a second boundary under a non-superuser runtime role. Migration/seed credentials are distinct from runtime credentials.

## Workflow and consistency
An evidence request owns a canonical record and multiple source documents. Submission returns HTTP 202; idempotency keys are tenant scoped and a replay with different content returns 409. Worker results include field-level source references, document digests, deterministic exceptions and extraction version. Text/CSV/JSON and text PDFs are supported; scanned PDFs explicitly require an OCR provider. Model output cannot update an approved record. Review uses optimistic version checks, validates completion and blocks approval of insufficient/exception-bearing results until remediated. Audit events are append-only; application and database triggers prevent updates/deletes. Hash chains detect modification, while documentation explicitly explains they are not an external notarization mechanism.

## Presentation and verification
Add an Operations view with persona selector, requests, source/field lineage, review actions, queue state and event history. A sample submission runs through the real persisted service and worker. Add security, concurrency, retry/recovery, idempotency and migration tests, including direct PostgreSQL RLS bypass attempts. A labeled offline evaluation corpus reports actual extraction metrics and adverse-input outcomes. Benchmarks record environment, workload, errors and latency percentiles; offline rules are not reported as LLM accuracy. Publish actual UI screenshots and result charts in README with links to ADRs, threat model, runbooks, cost model and ownership playbook.

## Boundaries
No paid services or real emails/messages are required. Email/Slack are adapter contracts/examples, not deployed integrations. AWS is a reference deployment, not an executed cloud benchmark. No invented incidents, users, historical commits or performance numbers. Production readiness gaps (SSO provisioning, OCR, object storage, retention enforcement, distributed tracing) are explicitly listed alongside implemented capabilities.
