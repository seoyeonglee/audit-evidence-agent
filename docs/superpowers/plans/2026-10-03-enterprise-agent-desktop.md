# Enterprise Audit Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing audit project with a persistent LangGraph review workflow and secure Electron local client, including actual application and test-report screenshots.

**Architecture:** FastAPI and the existing canonical record service remain authoritative. A tenant-scoped graph registry coordinates SQLite checkpoints, leased execution and durable review commands. The browser and Electron share the React Agent Runtime view; Electron main owns local files, sidecar lifecycle and validated API transport.

**Tech Stack:** Python/FastAPI/SQLAlchemy/LangGraph; React/TypeScript/Vite; Electron/TypeScript; pytest, PostgreSQL integration and Playwright browser/Electron tests.

**Spec:** `docs/superpowers/specs/2026-10-03-enterprise-agent-desktop-design.md`
**Approved spec commit:** `829104fc2954fa2d9e03cdc19e4eea4883eaf88a`
**Feature branch:** `feat/enterprise-agent-desktop`

## Global Constraints

- Default execution needs no API key, external model call, paid hosting, paid database, or paid signing service.
- Existing Operations, RAG Lab, canonical source facts, immutable approvals and audit history remain compatible.
- At most 20 snapshot documents; 200,000 characters per document; top-k at most 6; retry attempts capped at 3.
- One active run per request version/provider; server-generated run and thread IDs.
- Runs are tenant-scoped; identity and roles derive from bearer tokens, never caller-supplied tenant/role fields.
- Run states: queued, running, waiting_review, completed, failed, superseded.
- Human decisions: approve, reject, needs_changes; only an independent authorized reviewer may submit them.
- MVP graph checkpoint storage is per-tenant SQLite on one host; public free-host persistence may reset on redeploy.
- Electron uses contextIsolation=true, nodeIntegration=false, sandbox=true and named, bounded preload functions.
- Local imports: .txt/.csv/.json, strict UTF-8, regular non-symlink files, at most 1 MiB raw and 200,000 decoded characters.
- Python sidecar binds to 127.0.0.1 on a main-selected ephemeral port; its transport secret remains in main.
- Developer-runnable desktop app is in scope; no bundled Python, signed installer, VM sandbox or untested Windows/macOS claim.
- User explicitly requires both actual application screenshots and actual test-result screenshots; no mock screens or fabricated results.
- Do not merge to main to generate captures; keep the existing live deployment intact until the implemented PR is approved.

## Review Focus

1. Unicode filenames/content and byte-versus-character limits must work without leaking absolute paths — Task 5.
2. Empty/repeated retrieval hits and a document from another request must not produce fabricated or mixed citations — Task 2.
3. Simultaneous evidence submission and approval must produce one ordered, version-checked outcome — Task 3.
4. API/sidecar exit during polling must produce a recoverable UI state instead of a permanent loading screen — Tasks 4 and 6.
5. A repeated demo run with an already approved record must explain the blocked action and preserve the original record — Tasks 3 and 4.

---

## File structure and interfaces

| Unit | Files and responsibility |
|---|---|
| Run data | src/enterprise/schemas.py, models.py, registry.py: typed DTOs, tenant-scoped run/event/command records |
| Snapshot/context | src/enterprise/snapshot.py, context.py: immutable authorized input and request-scoped retrieval |
| Graph | src/enterprise/graph.py, nodes.py, checkpoints.py: bounded StateGraph, validation and per-tenant durable saves |
| Review/recovery | src/enterprise/review.py, runner.py, reports.py: transactional review command, leases and idempotent output |
| API | src/enterprise/routes.py; src/api.py router registration |
| Shared UI | frontend/src/enterprise/{types,client,AgentRuntime,platform}.ts(x), enterprise.css |
| Desktop trust boundary | desktop/src/{contracts,security,files,proxy,sidecar,main,preload}.ts |
| Evidence | tests/enterprise/, frontend/tests/enterprise.spec.ts, desktop/tests/, scripts/capture_test_reports.mjs |

DTO definitions in schemas.py: RunSnapshot, GraphState, Assessment, ReviewCommand, RunDetail. They use JSON-compatible scalars/lists/mappings and include run_id, request_id, snapshot_version, provider/version, source identifiers/digests, safe status/findings and event sequence. Secrets and local paths are never DTO fields.

### Task 1: Authorized run registry and immutable snapshots

**Files**
- Create: src/enterprise/__init__.py, schemas.py, models.py, snapshot.py, registry.py.
- Modify: src/platform/database.py and infrastructure/postgres/security.sql.
- Test: tests/enterprise/conftest.py, test_registry.py, test_postgres_registry.py.

**Interfaces**
- Consumes: Store.transaction(tenant_id), EvidenceService scope/request checks and existing request/document tables.
- Produces: RunRegistry(store), start(principal, request_id, expected_version, provider, key) -> RunDetail, detail(principal, run_id) -> RunDetail, list_for_request(principal, request_id) -> list[RunDetail].
- Produces: snapshot_request(conn, principal, request_id, expected_version) -> RunSnapshot.
- Produces: enterprise_fixture pytest fixture with a fresh store, two tenants, owner/reviewer identities and processed good/problem evidence requests.

- [ ] **Step 1:** Write tests: test_start_snapshot_is_immutable (later source changes do not alter stored snapshot); test_start_checks_role_scope_version_and_processing (403/404/409); test_limits_20_documents_and_200000_characters; test_duplicate_start_returns_same_run; test_changed_payload_same_key_conflicts; test_active_run_unique; test_registry_rls_under_non_bypass_role.
- [ ] **Step 2:** Run `python -m pytest tests/enterprise/test_registry.py -q`; expect missing-module/interface failures.
- [ ] **Step 3:** Implement DTOs, composite tenant FKs, registry tables, exact source snapshots, bounded provider values and start idempotency. Register metadata without changing existing record fields; extend PostgreSQL policies/grants for every new tenant table.
- [ ] **Step 4:** Run registry tests and the new PostgreSQL tests with TEST_POSTGRES_URL set to the isolated CI test database; require no denied-path leakage and one stable replay receipt.
- [ ] **Step 5:** Commit `feat: add scoped agent run registry and evidence snapshots`.

### Task 2: Genuine LangGraph assessment and durable interruption

**Files**
- Create: src/enterprise/context.py, nodes.py, graph.py, checkpoints.py.
- Modify: requirements.txt / requirements-dev.txt and reusable retrieval/reasoner adapters only where needed.
- Test: tests/enterprise/test_graph.py, test_checkpoint_restart.py, test_grounding.py.

**Interfaces**
- Consumes: RunSnapshot and GraphState from Task 1; existing exact parser findings and retrieval/reasoner interfaces.
- Produces: build_graph(checkpointer, provider="heuristic") -> compiled StateGraph.
- Produces: CheckpointManager(root: Path).open(tenant_id: str) -> context-managed SQLite saver.
- Produces: assessment nodes with signature (state: GraphState) -> dict; report-ready state contains the immutable review-command identifier.

- [ ] **Step 1:** Write test_real_graph_reaches_human_interrupt: expected nodes are load_snapshot, guardrails, retrieve, assess, validate_grounding, human_review; result exposes a persisted review interrupt and has no approved report.
- [ ] **Step 2:** Write test_new_process_loads_waiting_checkpoint and test_resume_uses_same_server_thread; test_fabricated_citation_blocks_approval; test_altered_span_or_digest_rejected; test_retrieval_cannot_mix_requests_or_tenants; test_empty_and_repeated_hits_have_explicit_findings; test_offline_profile_has_no_network_calls.
- [ ] **Step 3:** Run `python -m pytest tests/enterprise/test_graph.py tests/enterprise/test_checkpoint_restart.py tests/enterprise/test_grounding.py -q`; expect missing graph/checkpointer failures.
- [ ] **Step 4:** Resolve compatible current LangGraph/SQLite saver versions from official documentation, record pins, and implement the actual StateGraph with conditional safe failure/assessment paths and interrupt(). Hash server-owned tenant IDs to checkpoint filenames; enforce single-host profile. Reuse typed heuristic reasoning and scoped TF-IDF context; optional external provider is server-configured and disabled in offline/demo profiles.
- [ ] **Step 5:** Run the same tests; require persisted interruption to survive a separate process and quoted sources to match the frozen snapshot.
- [ ] **Step 6:** Commit `feat: orchestrate grounded review with durable LangGraph interrupts`.

### Task 3: Atomic human decisions, leased recovery and API

**Files**
- Create: src/enterprise/review.py, runner.py, reports.py, routes.py.
- Modify: src/platform/service.py (narrow reusable review transaction), src/api.py router registration.
- Test: tests/enterprise/test_review.py, test_recovery.py, test_api.py, test_concurrency.py.

**Interfaces**
- Consumes: Task 1 registry/snapshots and Task 2 graph/checkpoint manager.
- Produces: review_run(store, principal, run_id, expected_version, decision, feedback, key) -> ReviewCommand.
- Produces: GraphRunner(store, checkpoint_manager, tenant_id, clock=None).tick() -> bool.
- Produces: build_report(snapshot: RunSnapshot, assessment: Assessment, command: ReviewCommand) -> dict.
- Produces: create_router(store=None, checkpoint_manager=None, demo_enabled=False) -> APIRouter.
- Preserve EvidenceService.review(principal, request_id, version, decision, feedback); factor its transaction logic into review_in_transaction(conn, principal, request_id, version, decision, feedback, provenance=None) -> dict.

- [ ] **Step 1:** Write tests pinning atomic canonical review + immutable command; stale/self/non-reviewer/cross-tenant denial; unresolved-exception approval denial; source changes supersede pending run; duplicate identical decision returns the original command; conflicting replay returns 409; approved records cannot start new approval runs.
- [ ] **Step 2:** Write recovery tests: crash_after_review_before_resume, expired_runner_lease, stale_runner_fencing, retry_exhaustion_at_3, duplicate_finalize_one_report. Add PostgreSQL race tests for concurrent submit/review and duplicate commands; assert exactly one canonical review event.
- [ ] **Step 3:** Run `python -m pytest tests/enterprise/test_review.py tests/enterprise/test_recovery.py tests/enterprise/test_api.py tests/enterprise/test_concurrency.py -q`; expect interface failures.
- [ ] **Step 4:** Implement the relational review/outbox transaction and graph runner. Never mutate canonical records in a resumed graph node. Release lease at waiting_review; claim unconsumed review commands after restart; finalize one report per command. Use safe errors and increasing persisted event sequences.
- [ ] **Step 5:** Implement spec endpoints under /api/v2: POST request agent-runs, GET request agent-runs, GET run, GET run events?after=N, POST run review, GET run report. Public bounded graph ticks exist only with explicit DEMO_MODE. No client-provided thread/path/tenant authority.
- [ ] **Step 6:** Run new tests plus `python -m pytest tests/platform tests/test_agentic.py -q`; run PostgreSQL integration in CI; require existing approval and queue contracts to remain valid.
- [ ] **Step 7:** Commit `feat: recover graph review commands without duplicate approvals`.

### Task 4: Shared Agent Runtime view and real browser captures

**Files**
- Create: frontend/src/enterprise/types.ts, client.ts, platform.ts, AgentRuntime.tsx, enterprise.css.
- Modify: frontend/src/Workspace.tsx and shared API transport where needed.
- Test: frontend/tests/enterprise.spec.ts; fresh deterministic scenario seeding in tests/enterprise/fixtures.py.

**Interfaces**
- Consumes: Task 3 run APIs and immutable source/report DTOs.
- Produces: AgentRuntime component and EnterpriseTransport.request<T>(method, path, body?, idempotencyKey?) -> Promise<T>.
- Produces: browser transport via authenticated fetch; desktop transport detection through the named preload bridge, defined in Task 5.
- Produces: screenshots only after tested UI assertions, at docs/screenshots/agent-{waiting-review,approved,needs-changes,blocked-stale}.png.

- [ ] **Step 1:** Write browser tests for good evidence -> graph interrupt -> source inspection -> authorized approval -> export; conflicting/wrong-period evidence -> blocked approve -> needs_changes; unauthorized persona actions; stale snapshot; approved-record repeat explanation; API failure -> visible error -> successful retry.
- [ ] **Step 2:** Run `cd frontend && npx playwright test tests/enterprise.spec.ts`; expect missing Agent Runtime tab or controls.
- [ ] **Step 3:** Implement the new tab using existing visual conventions. Display real registry/node events, source quotes, provider, storage profile and input/current versions. Poll only while active; clean up on tab/run changes. Render safe error/retry controls; derive available decisions from server data and still handle server denial.
- [ ] **Step 4:** Add explicit fresh scenario setup per E2E test; never clear approved public records. Take page screenshots after assertions for the actual interrupted, completed, problem and stale states, not fabricated UI fixtures.
- [ ] **Step 5:** Run `npm run build` and existing plus new Playwright flows; inspect every new screenshot at desktop and mobile widths for clipping and readable citations.
- [ ] **Step 6:** Commit `feat: expose inspectable agent runs and human review in the workspace`.

### Task 5: Secure Electron IPC, local files and export

**Files**
- Create: desktop/package.json, tsconfig.json, src/contracts.ts, security.ts, files.ts, proxy.ts, preload.ts.
- Modify: frontend/src/enterprise/platform.ts and bridge type declaration.
- Test: desktop/tests/security.test.ts, files.test.ts, proxy.test.ts.

**Interfaces**
- Produces window.auditDesktop with runtimeStatus(), apiRequest(input), selectEvidence(), saveReport(runId).
- API input: { method: "GET" | "POST", path: string, body?: unknown, idempotencyKey?: string, bearerToken?: string }; main validates exact route allowlists and bounds before forwarding.
- selectEvidence() -> { cancelled: true } | { cancelled: false, filename: string, media_type: string, content: string }; never returns an absolute path.
- saveReport(runId: string) -> { saved: boolean }; main fetches an authorized completed report and performs its own save dialog.
- Trusted functions: readSelectedEvidence(path: string) -> Promise<SelectedEvidence>, validateApiRequest(input: unknown) -> ApiRequest, validateSender(event, allowedOrigin: string) -> void.

- [ ] **Step 1:** Write tests denying arbitrary route/URL, encoded traversal, unknown method, malformed body, unexpected sender/frame and unbounded payloads. File tests cover native-dialog cancellation, regular supported file, symlink, directory, invalid UTF-8, 1 MiB limit, 200,000-character limit and Korean filename/content.
- [ ] **Step 2:** Run `cd desktop && npm test`; expect unimplemented validators/readers.
- [ ] **Step 3:** Implement named contextBridge functions and main-owned dialogs; normalize and validate routes before proxying; validate file through its opened descriptor. Enforce UTF-8 and media type; keep sidecar credentials out of bridge responses and logs. Report save accepts run ID only, never an arbitrary renderer path/body.
- [ ] **Step 4:** Run desktop unit tests and TypeScript build; assert renderer-facing API omits Node primitives and local paths.
- [ ] **Step 5:** Commit `feat: constrain desktop IPC and selected evidence access`.

### Task 6: Local sidecar, actual Electron launch and desktop captures

**Files**
- Create: desktop/src/sidecar.ts, main.ts; src/enterprise/desktop_api.py; desktop/tests/runtime.spec.ts, playwright.config.ts.
- Modify: desktop/package.json build/dev/test scripts, frontend Vite asset base and CSP only as required for local packaged assets.
- Test/capture: docs/screenshots/desktop-{waiting-review,recovered,approved,local-import,startup-error}.png.

**Interfaces**
- Consumes: Tasks 3-5 API, shared view and restricted bridge.
- Produces: startSidecar(config: TrustedSidecarConfig) -> Promise<SidecarHandle>; SidecarHandle contains main-only baseUrl/transportSecret and stop(): Promise<void>.
- TrustedSidecarConfig: backend Python executable, repository root, private userData directory, startup timeout and explicit offline/demo profile.
- Produces desktop API entrypoint with transport-secret middleware on sidecar routes; existing API-role authorization remains independent.

- [ ] **Step 1:** Write tests for actual Electron BrowserWindow launch, no renderer require/process capability, denied unexpected navigation/window/permission request, and named bridge availability.
- [ ] **Step 2:** Write restart scenario: persist waiting_review, close app and owned backend, launch new Electron/backend instances using the same userData, assert same run/snapshot restored, approve and assert one report. Test sidecar startup failure/timeout and unexpected exit -> visible error/relaunch. Test selected local fixture import and completed report export through controlled dialog automation.
- [ ] **Step 3:** Run `cd desktop && npm run test:e2e` under Xvfb in Linux when necessary; expect missing launcher/lifecycle integration.
- [ ] **Step 4:** Implement loopback sidecar startup with ephemeral port selection/retry and random transport secret, readiness timeout, child-process cleanup and restart. Bind trusted Python configuration in main; set secure BrowserWindow flags and constrained CSP. Load built local assets, not the hosted public URL.
- [ ] **Step 5:** Run actual Electron tests and capture each screenshot only after its assertions. Include the Electron application window itself; a browser rendering the same React view is not desktop execution evidence.
- [ ] **Step 6:** Build the developer desktop artifact; record Python prerequisite. Verify Linux here/CI and state untested platforms accurately; do not represent a build-only Windows check as Windows runtime verification.
- [ ] **Step 7:** Commit `feat: run and recover the audit workspace in Electron`.

### Task 7: Reproducible verification, test-screen captures and portfolio evidence

**Files**
- Modify: .github/workflows/tests.yml, README.md, docs/ai-pipeline.md, THREAT_MODEL.md.
- Create: .github/workflows/enterprise-captures.yml, scripts/capture_test_reports.mjs, docs/adr/007-graph-canonical-boundary.md, docs/adr/008-desktop-ipc.md, docs/runbooks/graph-recovery.md, docs/runbooks/desktop-startup.md, docs/reports/enterprise-verification.json, eval/enterprise-corpus.json.
- Outputs: docs/screenshots/tests-{browser,desktop,backend}.png; reproducible raw test reports and workflow artifacts.

**Interfaces**
- Consumes: pytest JUnit XML, Playwright browser/Electron JSON+HTML reports and actual Task 4/6 captures.
- Produces: scripts/capture_test_reports.mjs CLI taking known local report paths and an output directory; returns nonzero if reports/screenshots are absent.
- Produces: enterprise-verification.json containing commit/environment/provider, commands, observed suite results, screenshot/report paths and persistence/platform limitations.

- [ ] **Step 1:** Add a small labeled corpus covering complete/missing/stale/conflicting/unsupported/instruction-like evidence and citation manipulation. Run the actual graph evaluator; store per-case outcomes and provider/version, never infer model accuracy from offline rule outcomes.
- [ ] **Step 2:** Configure CI jobs for existing backend, real PostgreSQL security/concurrency, frontend build/browser workflows and real Electron launch under Linux/Xvfb; upload reports and failed traces. Keep a manual capture workflow available for branch review.
- [ ] **Step 3:** Run required local checks and fresh-database browser/Electron suites, then inspect their exit status and raw reports. Capture browser and desktop Playwright HTML result pages after the real suites complete. Render actual pytest JUnit results into a clearly labeled local test-report page and capture it; include source JUnit artifact links.
- [ ] **Step 4:** Inspect all application and test-report images using view_image or equivalent. Fix unreadable text, clipped content and unclear states, then repeat only affected tests/captures.
- [ ] **Step 5:** Update README with actual screenshots, run commands, test-report evidence, design decisions and free-host/local persistence distinctions. Include an explicit offline provider label and developer desktop prerequisites.
- [ ] **Step 6:** Run final regression checks required by ENGINEERING_PLAYBOOK.md; record observed results with commit/environment and suite names. Obtain a whole-branch code review using the approved execution method, address substantive findings, and rerun affected checks.
- [ ] **Step 7:** Commit `docs: publish verified graph and desktop workflow evidence`; create a reviewable PR linking actual captures and CI. Main merge/live deploy remains a separate authorized integration step.

## Required capture manifest

| Image | What must actually be visible | Source proof |
|---|---|---|
| agent-waiting-review.png | Node stages, citations and persisted waiting-review state | Browser E2E + run API |
| agent-approved.png | Reviewer decision, completed report and source provenance | Browser E2E + one canonical event |
| agent-needs-changes.png | Concrete exception and recorded reviewer feedback | Problem-evidence E2E |
| agent-blocked-stale.png | Changed-version rejection and next action | Stale-version E2E |
| desktop-local-import.png | Imported local fixture and scoped source facts | Real Electron test |
| desktop-waiting-review.png / desktop-recovered.png | Same run before/after Electron + backend restart | Disk checkpoint + restart E2E |
| desktop-approved.png | Actual Electron window with completed reviewed report | Real Electron E2E |
| desktop-startup-error.png | Observable sidecar startup error and retry action | Real Electron failure test |
| tests-browser.png / tests-desktop.png | Actual suite names, results and test detail from HTML reports | Raw Playwright report artifacts |
| tests-backend.png | Clearly labeled pytest results with pass/fail/skips and environment | Raw JUnit artifact |

No screenshots exist yet. Completion claims require produced artifacts and passing observed checks.

## Self-review record

Spec coverage: data/control/source boundaries (Tasks 1-3), real interruption/recovery (2-3), API/roles (3), shared view and actual browser captures (4), secure IPC/local files (5), sidecar and actual Electron captures (6), optional provider/corpus/CI/documentation/test screens (2,7).
Interfaces: DTOs in Task 1; graph/checkpointer in 2; review/runner/API in 3; transport and UI in 4; named bridge in 5; sidecar in 6. Later tasks consume these exact contracts.
Review Focus: every listed failure condition has a named test in its owning task.
Scope: this is one integrated feature with backend/web milestones independently verifiable before desktop. No full rewrite, signed installer or paid infrastructure has been added.
Execution recommendation: Native, because these tasks share tight registry/DTO/transport interfaces; keeping implementation in one session reduces repeated context while retaining a final independent branch review.
