# Enterprise Audit Agent — LangGraph + Electron design

Date: 2026-10-03 (Asia/Seoul)
Repository: seoyeonglee/audit-evidence-agent
Baseline: e2580b836e454149c307d5d50a6899438cd58b45
Status: agreed in-chat design expanded for written-spec review; implementation has not started.

## 1. Intent and success

Build a reusable developer portfolio demonstration: an enterprise-oriented audit agent with genuine graph orchestration, persistent human review, inspectable evidence, and a secure desktop boundary. The user approved the proposed feature scope on 2026-10-03. This is useful beyond any particular employer.

Preserve the existing Operations workflow, deterministic source facts, tenant and role checks, queue leases, append-only approval history, and RAG Lab. Show implemented behavior with screenshots and reproducible tests rather than claiming customer deployments or employer work.

Default execution needs no API key, external model call, paid hosting, paid database, or paid signing service. The existing public web deployment remains the browser demo; Electron is a local desktop client. Local persistence and free-host ephemeral persistence must be labeled separately.

Success means a reviewer can run a graph on submitted evidence, inspect its stages and citations, close and reopen the local system while review is pending, approve or request changes under existing rules, and export the resulting source-backed report. Denied paths and recovery are demonstrated alongside the happy path.

## 2. Existing interfaces and chosen approach

The baseline has:
- React/TypeScript in frontend/, with Operations and RAG Lab tabs.
- FastAPI v2 operations, EvidenceService, relational records and a leased document worker.
- Deterministic extraction for normalized text/CSV/JSON, with source digest, line and quote.
- RAG Lab v1 with TF-IDF retrieval and heuristic or optional model reasoning.
- SQLite demo storage; PostgreSQL integration and RLS verified separately in CI.
- No LangGraph dependency or Electron client.

Chosen approach: add a Python LangGraph runtime beside the existing document worker, expose scoped run APIs, reuse the React workspace in web and desktop, and add a narrowly scoped Electron main/preload bridge. Do not rewrite the backend or replace canonical facts with model output.

Alternatives considered:
1. Electron wrapper around the hosted URL: small change, but does not demonstrate local files, local persistence or meaningful IPC boundaries.
2. Full TypeScript backend rewrite: unnecessary loss of existing Python extraction and security tests.
3. Python graph + shared React + local Electron client: reuses tested behavior and adds the intended engineering evidence; selected.

## 3. Boundaries and ownership

| Component | Owns | Does not own |
|---|---|---|
| Operations service | Identity, request scope, source records, canonical approval | Model interpretation |
| Existing document worker | Extraction queue, leases, facts and parser exceptions | Long human-review waits |
| Graph service/runner | Run registry, snapshots, graph execution, review interruption, recovery | Unchecked record mutation |
| LangGraph nodes | Retrieval, assessment, grounding, draft output | Arbitrary commands or authorization |
| React workspace | Run selection, stages, citations, review forms | Direct local file access |
| Electron main/preload | Validated file selection, local API lifecycle, bounded export | Arbitrary renderer IPC/network destinations |

Operations' current queue remains dedicated to document processing. Graph execution uses its own leased run registry; waiting for a human releases the execution lease and does not hold a database transaction or worker slot.

## 4. Graph behavior

Each run targets one existing request and a frozen request version, control definition, document set and content digests.

Nodes:
1. load_snapshot: confirm authorized request and completed document processing; load the immutable input snapshot.
2. guardrails: evaluate source facts, parser outcomes, period and unresolved exceptions.
3. retrieve: build request-scoped evidence context and retrieve control/guidance context.
4. assess: produce a typed advisory assessment with citations and missing-evidence reasons.
5. validate_grounding: verify cited identifiers and exact quoted spans against the snapshot.
6. human_review: use LangGraph interrupt() to persist a review payload and release execution.
7. finalize_report: consume the persisted, authorized human decision and create an idempotent report.

Guardrail problems do not become a confident pass. Assessment still explains missing/conflicting evidence when safe; unsupported citations make approval unavailable. Invalid source structure or a permanent runtime error terminates conservatively with a visible error code.

Human decisions are approve, reject or needs_changes. Approve requires a complete canonical record without open exceptions, validated sources, an independent reviewer and a matching request version. Reject/needs_changes record feedback without claiming evidence compliance.

The graph is a bounded assessment workflow, with allowlisted retrieval and reporting tools. There is no arbitrary shell, browser automation, recursive planning or unrestricted tool execution.

## 5. State and persistence

Graph state is a JSON-compatible typed schema:
run_id, request_id, snapshot_version, control_id, period, provider/version,
document digests and selected source spans, guardrail findings, retrieved sources,
assessment, grounding results, review-command reference and final report reference.

Never put bearer tokens, filesystem paths, API keys or raw environment variables in state.

The relational registry includes agent_runs, agent_run_events and agent_review_commands. Every row is tenant-scoped, references its request/run through composite tenant keys, and receives application authorization checks and PostgreSQL RLS where applicable.

Run states: queued, running, waiting_review, completed, failed, superseded.
Lease fields: token, expiry, attempts, available_at. Event fields include an increasing sequence, node, outcome, duration, input/output digest and safe error code.
Review commands have a unique idempotency key and immutable reviewer/decision/feedback data.

MVP graph checkpoints use the official SQLite saver in a separate application-owned checkpoint file per tenant. A server-controlled digest of tenant identity selects the file; no client path is accepted. Files live under a configured private runtime directory. All reads and writes go through the authenticated registry service, including checkpoint inspection; callers cannot submit a thread ID as authority.

Thread IDs are opaque server-generated run IDs. The graph runner serializes execution per run, leases registry rows, and validates its fencing token before committing registry changes. Nodes have no irreversible external side effects. A reclaimed run resumes its saved graph state instead of replaying an approved record mutation.

This checkpoint profile is a single-host reference implementation. It does not claim PostgreSQL-backed graph checkpoint isolation or distributed execution. Existing PostgreSQL Operations behavior remains supported. The graph runner must refuse a multi-host graph configuration rather than silently sharing unsafe SQLite files.

Local app storage survives restarts under Electron userData. Free Render redeploys may discard the SQLite registry and checkpoints; the public demo must state this. No paid persistence is provisioned.

## 6. Human review and recovery contract

A graph recommendation is never authorization. The review endpoint derives reviewer and tenant from the token, checks request/run scope, and rejects stale versions and self-approval.

To avoid an approval transaction and graph checkpoint becoming competing sources of truth:
- Refactor only the necessary EvidenceService review transaction boundary so the same validation and record mutation can participate in a graph review transaction.
- Atomically record the canonical review and an immutable graph resume command in the same relational transaction.
- Append the existing canonical audit event once, including the run/command identifiers as provenance.
- Resume the checkpoint separately using Command(resume=validated_command).
- Finalization reads the persisted command; it never calls canonical review again.
- A crash after approval but before graph resume leaves a recoverable command. Retry drains it and exports one report.
- A duplicate identical command returns the existing receipt. A changed payload with the same key returns 409.

Approval uses the input snapshot version; the resulting approved record version is recorded separately. New evidence before a decision makes the run superseded and prevents review. A new snapshot requires a new run. An approved canonical record remains immutable.

Never place approval writes before interrupt() inside a node: resuming can restart that node. Persist only safe, repeatable computations inside graph nodes.

## 7. API contract

All endpoints live under /api/v2 and use existing bearer identity.

| Endpoint | Contract |
|---|---|
| POST /requests/{id}/agent-runs | Start at current expected request version; reviewer/auditor only; idempotency header; reject processing or approved request |
| GET /requests/{id}/agent-runs | List runs within request scope |
| GET /agent-runs/{id} | Status, snapshot/version, assessment and safe source excerpts |
| GET /agent-runs/{id}/events?after=N | Persisted execution events after sequence N |
| POST /agent-runs/{id}/review | Reviewer only; expected snapshot version, idempotency header, decision and bounded feedback |
| GET /agent-runs/{id}/report | Completed report; scope checked; JSON or Markdown |

Start creates a queued registry entry; the runner executes outside HTTP transactions. The public synthetic demo can expose a bounded manual graph tick only under explicit DEMO_MODE, matching the existing document-worker demonstration.

Initial UI updates use short polling of persisted status/events. Stage durations come from actual execution; no fabricated animation or model-token streaming.

Limits: at most 20 snapshot documents, existing 200,000-character limit per document, top-k at most 6, one active run per request version/provider, bounded retry attempts of 3. More complex scheduling is outside this version.

## 8. Providers, retrieval and evidence

Default provider is explicitly labeled offline heuristic. LangGraph genuinely executes the workflow even without a hosted LLM; this is orchestration and rule-based reasoning, not a claim of model intelligence.

Refactor the existing retrieval/reasoner interfaces for reuse, supplying only the selected request's documents and trusted synthetic guidance. Do not retrieve from other requests/tenants or the global v1 evidence fixture.

An optional model adapter is configured server-side, never through renderer secrets. Public demo and offline desktop profile disable external model calls. A developer may explicitly enable the existing optional provider in a local backend; UI identifies this mode before submitting evidence. No new paid integration is needed for acceptance.

Canonical exact-source facts, probabilistic interpretation and reviewer conclusion are displayed separately. Quote/digest checks do not prove semantic entailment. Regex-based prompt detection is supplemental; evidence is untrusted data and cannot select tools, providers, roles or network policy.

## 9. Desktop profile

Add desktop/ using Electron + TypeScript and reuse the built frontend assets. Add an Agent Runtime tab that also works in the browser.

First release is a developer-runnable local app:
- Python dependencies and Node dependencies are installed using documented commands.
- Electron starts a Python FastAPI sidecar on 127.0.0.1 using a main-selected ephemeral port.
- The executable is selected in trusted launch configuration, never by renderer input.
- A one-time random desktop transport secret protects the sidecar and is held in main only.
- Main proxies allowlisted relative API routes and methods and supplies the transport secret; API role identity remains independently checked.
- Sidecar health is checked before showing the workspace; startup failures, timeouts and unexpected exits are visible.
- Application shutdown terminates the owned child process and leaves checkpoints and records for restart.
- No production auto-update, installer signing or bundled Python is claimed in this scope.

Package a desktop build artifact for inspection when CI supports it, but label whether it still needs a local Python environment. A self-contained signed Windows installer would be a separate deliverable.

## 10. Desktop security contract

BrowserWindow uses contextIsolation=true, nodeIntegration=false and sandbox=true.
Preload exposes named functions only: runtimeStatus, apiRequest, selectEvidence and saveReport. Never expose ipcRenderer, fs, shell, spawn or unrestricted fetch.

Validate IPC sender origin/frame, request schema, allowed method/route, payload length and response shape in main. Deny arbitrary URLs, external navigation, new windows and browser permission prompts. Use a constrained CSP for packaged frontend assets.

File selection is performed by a main-owned native dialog. Only the returned selection is read:
- Allow .txt, .csv and .json; use strict UTF-8 decoding and media-type validation.
- Reject non-regular files and symlinks; validate on the opened file descriptor.
- Cap raw size at 1 MiB and decoded content at the existing 200,000 characters.
- Return basename and contents, not the absolute path; renderer cannot request a later read by path.
- Reject encrypted/binary/unsupported content; PDF/OCR intake is excluded from this first desktop version.

Report export uses a main-owned save dialog and a server-produced completed report. No client-selected arbitrary overwrite path or executable output type is accepted.

Electron's renderer sandbox is a browser-process security feature. This project does not claim Hyper-V, a VM sandbox, kernel isolation, malware scanning or a certified air-gapped deployment.

## 11. UI and demonstration

Agent Runtime retains the existing visual language and adds:
- request selector, request version and source digest summary;
- real graph node/status timeline and interrupted-review state;
- side-by-side assessment, exact facts and citation/source inspection;
- approve/reject/needs-changes controls with explicit blocking reasons;
- provider and storage profile indicators;
- completed report export and visible recovery/error states;
- desktop-only local file import affordance, with browser feature detection.

Create bounded synthetic scenarios: complete access review, wrong period, conflicting evidence and instruction-like/unsupported source content. Document how to run these from a fresh local database; do not silently delete approved records to reset the public demo.

Screenshots capture actual run data. README should explain both what is implemented and how to reproduce it, with links to source, CI and the existing public demo.

## 12. Acceptance and verification

| Behavior | Required evidence |
|---|---|
| Real graph execution | Node/branch outcomes and grounded source IDs verified against fixtures |
| Human interruption | Run stops at waiting_review; independent process reconstructs it from disk |
| Resume after restart | New backend/runner instance resumes the same run and exports its report |
| Review safety | Owner/vendor/self-review/cross-tenant/stale-version attempts denied; allowed reviewer succeeds |
| Approval recovery | Crash after canonical approval but before graph resume; retry produces one review event and one report |
| Duplicate/concurrent review | Identical replay is stable; conflicting payload rejected; only one approval committed |
| Source boundaries | Invented citations, altered digest/span, request/tenant mixing and malformed output blocked |
| Runner recovery | Expired lease reclaimed; stale runner fenced; retry exhaustion visible |
| Desktop boundary | Real Electron launch, restricted preload, unauthorized sender/route/path requests denied |
| Desktop file/export | Selected supported text file imported; oversized/symlink/invalid UTF-8 blocked; report saved only through dialog |
| Compatibility | Existing backend/Operations/PostgreSQL tests, frontend build and browser flows pass |
| Portfolio output | Real screenshots, provider-labelled evaluation, CI artifacts and clear local-run instructions |

New tests target observable behavior and failure boundaries. Offline fixture metrics must not be relabeled LLM accuracy or production performance. Record dependency versions and environment with evidence. Check Electron on Linux in available runtime/CI; do not claim Windows/macOS runtime verification unless those OS jobs actually run.

## 13. File/module map and delivery order

Proposed additions:
- src/enterprise/: graph schema/nodes, registry, checkpoint manager, runner, routes, report.
- desktop/: main/preload, IPC schemas, API proxy, sidecar lifecycle and build scripts.
- frontend/src/enterprise/: run client, types, runtime view and shared platform adapter.
- tests/enterprise/ and desktop tests, plus frontend agent-runtime E2E.
- docs/adr/: graph-versus-canonical boundaries and desktop IPC decisions.
- docs/runbooks/: graph recovery and desktop startup.
- docs/screenshots/ and docs/reports/: measured evidence.

Targeted edits: platform models/migration/RLS for the registry, reusable review transaction interface, API router registration, provider/retrieval adapters, workspace navigation, dependency manifests and CI. Keep unrelated extraction/queue changes out of scope.

Delivery order after written-spec and plan review:
1. Scoped registry/checkpoints and graph behavior.
2. Authorized review/outbox recovery and run API.
3. Shared web Agent Runtime view and regression verification.
4. Secure Electron local profile and actual desktop tests.
5. README/screenshots/evaluation evidence and reviewable PR.
6. Existing free web deployment verification when the implemented change is approved for main.

Do not merge to main merely to create screenshots. Existing Render auto-deployment is tied to main; feature-branch documentation or implementation does not change that live service.

## 14. References and limits

Official references checked during design:
- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://docs.langchain.com/oss/python/langgraph/persistence
- https://www.electronjs.org/docs/latest/tutorial/security
- https://www.electronjs.org/docs/latest/tutorial/process-model

Implementation must resolve compatible versions from current official docs and pin reproducible dependencies. Persistent review, scoped execution and security boundaries are the substantive claims; UI polish and synthetic metrics must not substitute for them.

Self-review completed: explicit MVP, local and hosted storage distinction, review/checkpoint consistency, replay semantics, failure paths, role/source boundaries, desktop deliverable limits and acceptance criteria. No production/VM/Windows-signing claim is implied.
