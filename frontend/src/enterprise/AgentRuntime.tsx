import { useEffect, useState } from "react";
import { enterprise } from "./client";
import { request } from "./platform";
import type { Session, Run, EvidenceRequest } from "./types";
import "./enterprise.css";
const STEPS = [
  "load_snapshot",
  "guardrails",
  "retrieve",
  "assess",
  "validate_grounding",
  "human_review",
  "finalize_report",
];
const label = (s: string) => s.replaceAll("_", " ");
export default function AgentRuntime() {
  const [session, setSession] = useState<Session>();
  const [persona, setPersona] = useState("reviewer");
  const [requests, setRequests] = useState<EvidenceRequest[]>([]);
  const [selected, setSelected] = useState("");
  const [run, setRun] = useState<Run>();
  const [scenario, setScenario] = useState("complete");
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [desktopStatus, setDesktopStatus] = useState("");
  const [notice, setNotice] = useState("");
  const chosen = requests.find((r) => r.id === selected);
  useEffect(() => {
    let alive = true;
    enterprise
      .session(persona)
      .then(async (s) => {
        const rs = await enterprise.requests(s.token);
        if (!alive) return;
        setSession(s);
        setRequests(rs.requests);
        if (window.auditDesktop)
          setDesktopStatus((await window.auditDesktop.runtimeStatus()).status);
        const last =
          persona === "reviewer"
            ? localStorage.getItem("agent-last-run")
            : null;
        if (last) {
          try {
            const r = await enterprise.detail(s.token, last);
            if (alive) {
              setRun(r);
              setSelected(r.request_id);
            }
          } catch {
            localStorage.removeItem("agent-last-run");
          }
        }
      })
      .catch((e) => alive && setError(e.message));
    if (window.auditDesktop)
      window.auditDesktop
        .runtimeStatus()
        .then((s) => setDesktopStatus(s.status));
    return () => {
      alive = false;
    };
  }, [persona]);
  useEffect(() => {
    if (
      !run ||
      !session ||
      ["completed", "failed", "superseded"].includes(run.status)
    )
      return;
    let alive = true;
    const timer = setInterval(
      () =>
        enterprise
          .detail(session.token, run.id)
          .then((r) => alive && setRun(r))
          .catch((e) => alive && setError(e.message)),
      1200,
    );
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [run?.id, run?.status, session?.token]);
  useEffect(() => {
    if (!selected || !session) return;
    let alive = true;
    enterprise
      .runs(session.token, selected)
      .then(async (result) => {
        if (!result.runs.length) return;
        const restored = await enterprise.detail(
          session.token,
          result.runs[0].id,
        );
        if (!alive) return;
        setRun(restored);
        localStorage.setItem("agent-last-run", restored.id);
      })
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [selected, session?.token]);
  async function action(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setBusy(false);
    }
  }
  async function refresh() {
    // A synthetic backend restart rotates demo tokens. Retry reacquires the
    // selected persona and reloads reads without replaying any mutation.
    const s = await enterprise.session(persona);
    const rs = await enterprise.requests(s.token);
    setSession(s);
    setRequests(rs.requests);
    if (window.auditDesktop)
      setDesktopStatus((await window.auditDesktop.runtimeStatus()).status);
    if (run) setRun(await enterprise.detail(s.token, run.id));
  }
  async function create() {
    if (!session) return;
    const r = await enterprise.scenario(session.token, scenario);
    setRequests((rs) => [r, ...rs]);
    setSelected(r.id);
    setRun(undefined);
    localStorage.removeItem("agent-last-run");
    setFeedback("");
  }
  async function start() {
    if (!session || !chosen) return;
    const r = await enterprise.start(session.token, chosen);
    setRun(await enterprise.detail(session.token, r.id));
    localStorage.setItem("agent-last-run", r.id);
  }
  async function process() {
    if (!session || !run) return;
    await enterprise.process(session.token);
    setRun(await enterprise.detail(session.token, run.id));
    await refresh();
  }
  async function review(decision: string) {
    if (!session || !run) return;
    await enterprise.review(
      session.token,
      run,
      decision,
      feedback,
      crypto.randomUUID(),
    );
    setRun(await enterprise.detail(session.token, run.id));
    await refresh();
  }
  async function exportReport() {
    if (!session || !run) return;
    if (window.auditDesktop) {
      const result = await window.auditDesktop.saveReport(run.id);
      if (result.saved) setNotice("Report saved to the selected file.");
      return;
    }
    const data = await enterprise.report(session.token, run.id);
    const u = URL.createObjectURL(
      new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = u;
    a.download = `audit-${run.id}.json`;
    a.click();
    URL.revokeObjectURL(u);
  }
  async function importEvidence() {
    if (!session || !chosen || !window.auditDesktop) return;
    const file = await window.auditDesktop.selectEvidence();
    if (file.cancelled) return;
    const owner = await enterprise.session("owner");
    await request(
      "POST",
      `/api/v2/requests/${chosen.id}/documents`,
      owner.token,
      {
        filename: file.filename,
        media_type: file.media_type,
        content: file.content,
      },
      crypto.randomUUID(),
    );
    // Explicit synthetic owner import; reviewer identity remains unchanged.
    await request("POST", "/api/v2/demo/process", session.token, {});
    await refresh();
  }
  const pending = run?.status === "waiting_review" && !run.review;
  const allowed = pending && session?.role === "reviewer" && !run?.stale;
  const approval =
    allowed && run?.grounding.valid && run?.snapshot.canonical.complete;
  return (
    <main className="agent-shell">
      <div className="agent-topline">
        <span>ENTERPRISE AGENT / LOCAL-FIRST REFERENCE</span>
        <span className="agent-dot">
          {window.auditDesktop
            ? `ELECTRON · ${desktopStatus || "connecting"}`
            : "WEB WORKSPACE"}
        </span>
      </div>
      <header className="agent-hero">
        <div>
          <div className="agent-kicker">SOURCE-BACKED EXECUTION</div>
          <h1>
            Agent<span> / </span>Runtime
          </h1>
          <p>
            Evidence becomes a reviewable decision.
            <br />
            Every step persisted. Every approval accountable.
          </p>
        </div>
        <div className="agent-profile">
          <strong>OFFLINE HEURISTIC</strong>
          <span>LangGraph · SQLite checkpoints</span>
          <small>No external model calls · synthetic data only</small>
        </div>
      </header>
      <div className="agent-stats">
        <div>
          <span>EXECUTION STATE</span>
          <strong data-testid="run-status">
            {run?.status || "not_started"}
          </strong>
        </div>
        <div>
          <span>VERIFIED CITATIONS</span>
          <strong>
            {run?.grounding.checked_sources ?? 0}
            <small> / exact source checks</small>
          </strong>
        </div>
        <div>
          <span>SNAPSHOT VERSION</span>
          <strong>
            {run?.snapshot_version ?? "—"}
            <small>
              {" "}
              / current {run?.current_version ?? chosen?.version ?? "—"}
            </small>
          </strong>
        </div>
        <div>
          <span>STORAGE PROFILE</span>
          <strong>
            {window.auditDesktop ? "Local durable" : "Demo ephemeral"}
          </strong>
        </div>
      </div>
      {notice && (
        <div role="status" className="agent-alert">
          {notice}
        </div>
      )}
      {error && (
        <div role="alert" className="agent-alert">
          <strong>Action could not finish</strong>
          <span>{error}</span>
          <button onClick={() => action(refresh)}>Retry connection</button>
        </div>
      )}
      <div className="agent-grid">
        <aside className="agent-panel agent-input">
          <div className="agent-panel-title">
            <span>01 / EVIDENCE CONTEXT</span>
            <span>SCOPED</span>
          </div>
          <label>
            Session
            <select
              aria-label="Session persona"
              value={persona}
              onChange={(e) => {
                setRun(undefined);
                setSelected("");
                setSession(undefined);
                setPersona(e.target.value);
              }}
            >
              <option value="reviewer">Reviewer · Maya Chen</option>
              <option value="owner">Owner · Alex Rivera</option>
              <option value="vendor">Vendor · Jordan Vale</option>
              <option value="other-reviewer">Other org · Nora Kim</option>
            </select>
          </label>
          <label>
            Request
            <select
              aria-label="Evidence request"
              value={selected}
              onChange={(e) => {
                setSelected(e.target.value);
                setRun(undefined);
              }}
            >
              <option value="">Select a processed request</option>
              {requests.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.title} · {r.status}
                </option>
              ))}
            </select>
          </label>
          {chosen && (
            <div className="agent-request">
              <span>{chosen.id}</span>
              <h3>{chosen.title}</h3>
              <p>
                {chosen.status} · version {chosen.version}
              </p>
            </div>
          )}
          <button
            className="agent-primary"
            disabled={
              busy ||
              !chosen ||
              !["reviewer", "auditor"].includes(session?.role ?? "") ||
              ["approved", "processing", "awaiting_evidence"].includes(
                chosen?.status ?? "",
              )
            }
            onClick={() => action(start)}
          >
            Start agent run
          </button>
          {chosen?.status === "approved" && !run && (
            <p className="agent-note">
              Approved records are immutable. Create a new demo request to
              repeat the workflow.
            </p>
          )}
          {window.auditDesktop && (
            <button
              disabled={
                busy ||
                !chosen ||
                chosen.status === "approved" ||
                session?.role !== "reviewer"
              }
              onClick={() => action(importEvidence)}
            >
              Import local evidence
            </button>
          )}
          <div className="agent-demo">
            <span className="agent-kicker">REPRODUCIBLE SCENARIOS</span>
            <label>
              Demo scenario
              <select
                aria-label="Demo scenario"
                value={scenario}
                onChange={(e) => setScenario(e.target.value)}
              >
                <option value="complete">Complete access review</option>
                <option value="period">Stale reporting period</option>
                <option value="conflict">Conflicting source values</option>
                <option value="quarantine">Instruction-like evidence</option>
              </select>
            </label>
            <button
              disabled={
                busy ||
                session?.role !== "reviewer" ||
                session.tenant_id !== "demo-acme"
              }
              onClick={() => action(create)}
            >
              Create demo request
            </button>
            <p>
              Creates a new fictional request. Existing approvals remain intact.
            </p>
          </div>
        </aside>
        <section className="agent-panel agent-execution">
          <div className="agent-panel-title">
            <span>02 / GRAPH EXECUTION</span>
            <span>LIVE RECORDS</span>
          </div>
          <div className="agent-execution-head">
            <h2>{run?.snapshot.title || "Ready when evidence is ready"}</h2>
            <button
              disabled={
                busy ||
                !run ||
                session?.role !== "reviewer" ||
                ["completed", "failed", "superseded"].includes(
                  run?.status ?? "",
                )
              }
              onClick={() => action(process)}
            >
              Execute graph
            </button>
          </div>
          <div className="agent-timeline">
            {STEPS.map((step, i) => {
              const events = run?.events?.filter((e) => e.node === step) ?? [];
              const last = events.at(-1);
              return (
                <div
                  key={step}
                  className={`agent-step ${last?.outcome === "complete" ? "done" : last ? "paused" : ""}`}
                >
                  <span className="agent-step-index">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <strong>{label(step)}</strong>
                    <span>{last?.outcome ?? "not executed"}</span>
                  </div>
                  <small>{last ? `${last.duration_ms} ms` : "—"}</small>
                  <b>{last?.outcome === "complete" ? "✓" : last ? "Ⅱ" : "·"}</b>
                </div>
              );
            })}
          </div>
          <div className="agent-assessment">
            <span className="agent-kicker">ADVISORY ASSESSMENT</span>
            <h3>
              {run?.assessment.recommendation
                ? label(run.assessment.recommendation)
                : "No assessment yet"}
            </h3>
            <p>
              {run?.assessment.summary ||
                "Start an execution to retrieve evidence and validate exact sources."}
            </p>
            {run?.assessment.missing_evidence?.map((m, i) => (
              <p className="agent-warning" key={i}>
                {m}
              </p>
            ))}
            {run?.grounding.errors?.map((e) => (
              <p className="agent-warning" key={e}>
                {e}
              </p>
            ))}
          </div>
        </section>
        <aside className="agent-panel agent-review">
          <div className="agent-panel-title">
            <span>03 / HUMAN CONTROL</span>
            <span>REQUIRED</span>
          </div>
          <div className="agent-review-status">
            {run?.review
              ? "Review recorded"
              : pending
                ? "Waiting for independent review"
                : "Review follows source verification"}
          </div>
          <label>
            Reviewer feedback
            <textarea
              aria-label="Reviewer feedback"
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="Explain which sources support your decision…"
              maxLength={1000}
            />
          </label>
          <button
            className="agent-primary"
            disabled={busy || !approval}
            onClick={() => action(() => review("approve"))}
          >
            Approve record
          </button>
          <div className="agent-decision-pair">
            <button
              disabled={busy || !allowed}
              onClick={() => action(() => review("needs_changes"))}
            >
              Request changes
            </button>
            <button
              disabled={busy || !allowed}
              onClick={() => action(() => review("reject"))}
            >
              Reject
            </button>
          </div>
          {pending && !approval && (
            <p className="agent-warning">
              {run?.stale
                ? "Snapshot changed. Start a new run for the current evidence."
                : "Approval blocked until source gaps and exceptions are resolved."}
            </p>
          )}
          {run?.review && (
            <div className="agent-review-receipt">
              <span>
                {label(run.review.decision)} · {run.review.reviewer}
              </span>
              <p>{run.review.feedback || "No additional feedback"}</p>
              <small>
                Persisted command · resumes without another approval
              </small>
            </div>
          )}
          <button
            disabled={busy || run?.status !== "completed"}
            onClick={() => action(exportReport)}
          >
            Export report
          </button>
          <p className="agent-note">
            Interpretation is advisory. Server role, version and source checks
            govern approval.
          </p>
        </aside>
      </div>
      <section className="agent-panel agent-sources">
        <div className="agent-panel-title">
          <span>04 / EXACT SOURCE PROVENANCE</span>
          <span>FACTS ≠ MODEL CONFIDENCE</span>
        </div>
        <div className="agent-source-grid">
          {Object.entries(run?.snapshot.canonical.fields ?? {}).map(
            ([field, fact]) => (
              <article key={field}>
                <span>{label(field)}</span>
                <strong>{String(fact.value)}</strong>
                <blockquote>{fact.source.quote}</blockquote>
                <small>Line {fact.source.line} · original evidence</small>
              </article>
            ),
          )}
          {!run && (
            <p className="agent-note">
              Source facts, original excerpts and document digests appear here
              after a run is registered.
            </p>
          )}
        </div>
        {run && (
          <div className="agent-digests">
            {run.snapshot.documents.map((d) => (
              <span key={d.id}>
                {d.filename} <code>SHA256 {d.digest}</code>
              </span>
            ))}
          </div>
        )}
      </section>
      <footer className="agent-footer">
        <span>
          {run ? `RUN ${run.id}` : "LANGGRAPH / INSPECTABLE BY DESIGN"}
        </span>
        <span>
          Synthetic reference · exact quotes do not prove semantic compliance
        </span>
      </footer>
    </main>
  );
}
