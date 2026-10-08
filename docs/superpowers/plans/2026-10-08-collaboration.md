# Evidence Collaboration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Complete request-scoped external participation and immutable evidence revisions with independent reapproval.

**Architecture:** Extend the existing modular monolith with a collaboration service and additive tables. Keep the leased worker and append-only events; preserve worker job-before-request lock ordering. The fresh checkout is dedicated to this change.

**Tech Stack:** React, TypeScript, FastAPI, SQLAlchemy, SQLite, PostgreSQL, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-08-collaboration-design.md`

## Global Constraints
- Invitations default to 24 hours and never exceed 7 days; accepted external sessions expire with their invitation.
- Store only invitation/session token hashes; URL fragments, no-referrer and no-store protect token transport.
- Only reviewers issue/revoke invitations or reopen approval; external sessions submit only to their one assigned request.
- Preserve all original documents and approval events. Superseded documents do not contribute to the current canonical record.
- Preserve existing tenant isolation, self-approval prohibition, idempotency and worker fencing.
- No email dispatch, paid services, whole-app framework migration, or employer/customer data.

## Review Focus
- Scanner GET requests must never consume an invitation.
- Simultaneous accept/revoke must not leave an authorized revoked session.
- Replayed document submissions must not create another revision.
- A queued/running extraction must not be superseded and later overwrite current facts.
- Failed/dead-letter superseded sources must not permanently block approval of their valid replacement.

### Task 1: Invitation persistence and authorization
**Files:** modify `src/platform/models.py`, `src/platform/service.py`, `infrastructure/postgres/security.sql`; create `src/platform/collaboration.py`, `tests/platform/test_collaboration.py`.
**Interfaces:** `CollaborationService.create_invitation(principal, request_id, ttl_hours=24)`, `accept_invitation(token, name)`, `revoke_invitation(principal, request_id, invitation_id)`; responses include public metadata and one-time plaintext token only on creation/acceptance.
- [ ] Write failing tests for 24-hour default, 7-day maximum, request-only scope, concurrent acceptance, expiry and revocation of issued sessions.
- [ ] Run `python -m pytest tests/platform/test_collaboration.py -q`; confirm new behavior fails.
- [ ] Add invitation and external-session tables with tenant/request composite foreign keys; add RLS policies. Use secrets.token_urlsafe(32), hashed tokens and transactional row locking. Resolve external identity using a signed tenant locator plus DB validation so runtime RLS does not require unrestricted session lookup.
- [ ] Extend Principal with optional request/session scope; enforce it in every service query. Authenticate against revocation and expiration on every call.
- [ ] Run invitation tests and existing platform tests; commit the tested change.

### Task 2: Immutable revisions and reapproval
**Files:** modify `src/platform/service.py`, `src/platform/worker.py`, `src/platform/models.py`; create `tests/platform/test_revisions.py`.
**Interfaces:** `submit(..., replaces_document_id=None)` and `reopen(principal, request_id, version, reason)`; detail exposes revision links and current/previous approval state.
- [ ] Write failing tests for same-request replacement, active-leaf replacement only, idempotent replay, retained source history, corrected conflicts, dead-letter replacement, stale version and independent reapproval.
- [ ] Run `python -m pytest tests/platform/test_revisions.py -q`; confirm new assertions fail.
- [ ] Add a document-replacement relation with uniqueness and same-tenant/request foreign keys. Permit revisions only for authorized submitters on non-approved requests. Reject replacement while any request job is queued/running.
- [ ] Keep existing job-before-request locking when checking pending jobs; lock/revalidate inside one transaction. Reopen requires nonempty reason, reviewer role and exact version; clear current canonical approval readiness until recomputation.
- [ ] Filter superseded documents and their jobs from worker canonical/terminal calculations. Preserve old events and documents; append revision and reopen events.
- [ ] Run revision, recovery, worker and workflow tests; commit the tested change.

### Task 3: API and complete browser workflow
**Files:** modify `src/platform/routes.py`, `frontend/src/operations/Operations.tsx`, `frontend/src/operations/client.ts`, `frontend/src/operations/types.ts`, `frontend/src/operations/operations.css`; create `frontend/src/operations/Invitation.tsx`, `frontend/tests/collaboration.spec.ts`.
**Interfaces:** POST/GET `/requests/{id}/invitations`, POST `/requests/{id}/invitations/{invite_id}/revoke`, POST `/invitations/accept`, POST `/requests/{id}/reopen`; DocumentInput gains optional `replaces_document_id`.
- [ ] Write API rejection tests for malformed tokens, scanner GET, repeated acceptance, forbidden roles and cross-request revisions.
- [ ] Add validated endpoints, no-store token responses and bounded anonymous acceptance attempts (persisted limiter); apply no-referrer to frontend HTML.
- [ ] Add invitation creation/list/revocation, explicit acceptance, request-only external workspace, replacement selection, version comparison and reopen-with-reason UI. Read and erase token fragment before loading a session; do not persist raw tokens in logs or reports.
- [ ] Add Playwright scenario using separate reviewer and external browser contexts: invite→accept→submit→process→needs changes→replace→approve→reopen→replace→reapprove. Assert external context cannot review or switch personas.
- [ ] Run backend tests, `npm run build` and `npx playwright test`; capture desktop/mobile states and commit.

### Task 4: PostgreSQL, release evidence and delivery
**Files:** modify `tests/platform/test_postgres.py`, `README.md`, `docs/runbooks/release-and-restore.md`; create `docs/reports/collaboration-verification.json`.
- [ ] Add real runtime-role tests for new-table unfiltered RLS, cross-tenant inserts, concurrent accept/revoke and stale revision races.
- [ ] Run full backend suite, Ruff checks, frontend build/browser suites and real PostgreSQL tests; record commands, environment, exact pass/skip counts and limitations.
- [ ] Test additive migration against an existing database with approved evidence; verify original documents and audit chain remain unchanged. Document that rollback disables new endpoints and preserves additive tables/history.
- [ ] Review full diff for token leakage, lock ordering and approval bypass. Record findings and corrections.
- [ ] Publish a reviewable branch/PR under existing authorization; merge/deploy only with applicable user authorization. Verify public deployed workflow, update screenshots and link code/test/deployment evidence. If authorization or account access blocks delivery, report exact remaining step.

## Execution
Recommended: implement directly in the current session. The tasks share authorization and worker invariants, so keeping one implementation context avoids interface drift. Do not add subagents unless explicitly selected by the user.
