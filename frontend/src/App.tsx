import { useEffect, useMemo, useState } from "react";

import { api } from "./api";
import type { Detail, Overview, QueueItem, Source } from "./types";

function pct(value: number | undefined) {
  if (value === undefined || Number.isNaN(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

function statusLabel(value: string) {
  return value.replace("_", " ").toUpperCase();
}

function truncate(value: string, length = 60) {
  return value.length <= length ? value : value.slice(0, length - 1) + "…";
}

function App() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [selectedId, setSelectedId] = useState("CH-01");
  const [detail, setDetail] = useState<Detail | null>(null);
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);
  const [feedback, setFeedback] = useState("");
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState(false);
  const [notice, setNotice] = useState("Running deterministic checks and grounded retrieval…");
  const [error, setError] = useState("");

  async function loadOverview() {
    const next = await api.overview();
    setOverview(next);
    if (!next.queue.some((item) => item.control_id === selectedId) && next.queue.length) {
      setSelectedId(next.queue[0].control_id);
    }
  }

  async function loadDetail(controlId: string) {
    setLoading(true);
    setError("");
    try {
      const next = await api.detail(controlId);
      setDetail(next);
      setSelectedSource(next.retrieval.sources.find((source) => source.cited) ?? next.retrieval.sources[0] ?? null);
      setFeedback(next.review.feedback ?? "");
      setNotice(`${controlId} assessment loaded · ${next.retrieval.sources.length} retrieved sources · ${next.decision.citations.length} cited`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load assessment.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    (async () => {
      try {
        await loadOverview();
        await loadDetail("CH-01");
      } catch (err) {
        setError(err instanceof Error ? err.message : "API unavailable.");
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function chooseControl(item: QueueItem) {
    setSelectedId(item.control_id);
    await loadDetail(item.control_id);
  }

  async function submitReview(decision: "approve" | "needs_changes" | "reject") {
    if (!detail) return;
    setReviewing(true);
    setError("");
    try {
      const result = await api.review(detail.control.control_id, decision, feedback);
      setDetail({ ...detail, review: result.review });
      await loadOverview();
      setNotice(`Human review recorded: ${decision.replace("_", " ").toUpperCase()}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review action failed.");
    } finally {
      setReviewing(false);
    }
  }

  const evaluation = overview?.evaluation ?? {};
  const citedCount = detail?.retrieval.sources.filter((source) => source.cited).length ?? 0;
  const evidence = detail?.evidence[0];

  const coverageItems = useMemo(() => {
    if (!detail) return [];
    return [
      { label: "Evidence type", pass: detail.baseline.evidence_type_match, value: detail.control.required_evidence_type },
      { label: "Target period", pass: detail.baseline.period_match, value: detail.control.target_period },
      { label: "Keyword coverage", pass: detail.baseline.keyword_coverage >= 0.5, value: pct(detail.baseline.keyword_coverage) },
      { label: "Exception scan", pass: detail.baseline.exception_terms.length === 0, value: detail.baseline.exception_terms.length ? detail.baseline.exception_terms.join(", ") : "No explicit exception" },
    ];
  }, [detail]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon"><span>CR</span></div>
          <div>
            <strong>CONTROL//ROOM</strong>
            <small>Audit Evidence Agent</small>
          </div>
        </div>
        <div className="topbar-center">
          <span className="workspace-name">{overview?.workspace.name ?? "Loading workspace…"}</span>
          <span className="period">{overview?.workspace.period ?? "—"}</span>
        </div>
        <div className="top-actions">
          <span className="mode"><i /> HEURISTIC RAG · ONLINE</span>
          <span className="synthetic">SYNTHETIC ONLY</span>
          <a href={api.baseUrl + "/docs"} target="_blank" rel="noreferrer">API ↗</a>
          <a href="https://github.com/seoyeonglee/audit-evidence-agent" target="_blank" rel="noreferrer">GITHUB ↗</a>
        </div>
      </header>

      <section className="eval-strip">
        <div className="eval-title">
          <span>MODEL / PIPELINE EVALUATION</span>
          <small>{overview?.workspace.run_id || "initializing"}</small>
        </div>
        <div className="eval-metric"><span>STATUS ACCURACY</span><strong>{pct(evaluation.exact_status_accuracy)}</strong></div>
        <div className="eval-metric"><span>EXCEPTION PRECISION</span><strong>{pct(evaluation.exception_precision)}</strong></div>
        <div className="eval-metric"><span>EXCEPTION RECALL</span><strong>{pct(evaluation.exception_recall)}</strong></div>
        <div className="eval-metric"><span>GROUNDED RATE</span><strong>{pct(evaluation.grounded_rate)}</strong></div>
        <div className="eval-metric"><span>CITATION VALID</span><strong>{pct(evaluation.citation_valid_rate)}</strong></div>
        <div className="eval-metric safe"><span>HALLUCINATION PROXY</span><strong>{pct(evaluation.hallucination_proxy_rate)}</strong></div>
      </section>

      <div className="layout">
        <aside className="queue-panel">
          <div className="queue-head">
            <div>
              <span className="eyebrow">REVIEW QUEUE</span>
              <h2>Control assessments</h2>
            </div>
            <span className="queue-count">{overview?.summary.controls ?? "—"}</span>
          </div>

          <div className="queue-summary">
            <div><span>SUPPORTED</span><strong>{overview?.summary.supported ?? "—"}</strong></div>
            <div><span>PARTIAL</span><strong>{overview?.summary.partial ?? "—"}</strong></div>
            <div><span>MISSING</span><strong>{overview?.summary.missing ?? "—"}</strong></div>
          </div>

          <div className="queue-list">
            {overview?.queue.map((item) => (
              <button
                key={item.control_id}
                className={`queue-item ${item.control_id === selectedId ? "active" : ""}`}
                onClick={() => void chooseControl(item)}
              >
                <div className="queue-item-top">
                  <span className="control-code">{item.control_id}</span>
                  <span className={`status ${item.status}`}>{statusLabel(item.status)}</span>
                </div>
                <strong>{item.title}</strong>
                <div className="queue-item-foot">
                  <span>CONF {Math.round(item.confidence * 100)}%</span>
                  <span>BASE {item.baseline_score}</span>
                  <span className={item.review_status === "completed" ? "reviewed" : ""}>
                    {item.review_status === "completed" ? "✓ REVIEWED" : "○ PENDING"}
                  </span>
                </div>
              </button>
            ))}
          </div>

          <div className="queue-footer">
            <span>HUMAN REVIEW</span>
            <strong>{overview?.summary.pending_review ?? "—"} pending</strong>
            <small>AI output is never the final audit conclusion.</small>
          </div>
        </aside>

        <main className="workspace">
          {error && <div className="error-banner">{error}</div>}
          <div className="activity-banner">
            <span className="pulse" />
            <strong>{loading ? "PROCESSING CONTROL…" : notice}</strong>
            <span>{overview?.workspace.framework}</span>
          </div>

          <section className="control-hero panel">
            <div className="control-heading">
              <div>
                <span className="eyebrow">CONTROL REQUIREMENT</span>
                <div className="title-line">
                  <span className="control-id">{detail?.control.control_id ?? "—"}</span>
                  <h1>{detail?.control.title ?? "Loading assessment…"}</h1>
                </div>
                <p>{detail?.control.requirement}</p>
              </div>
              <div className="control-meta">
                <div><span>EVIDENCE TYPE</span><strong>{detail?.control.required_evidence_type ?? "—"}</strong></div>
                <div><span>PERIOD</span><strong>{detail?.control.target_period ?? "—"}</strong></div>
                <div><span>PROVIDER</span><strong>{detail?.trace.provider ?? "—"}</strong></div>
              </div>
            </div>
            <div className="keywords">
              {detail?.control.keywords.map((keyword) => <span key={keyword}>{keyword}</span>)}
            </div>
          </section>

          <section className="main-grid">
            <div className="left-stack">
              <section className="panel assessment-panel">
                <div className="panel-head">
                  <div>
                    <span className="eyebrow">AGENT ASSESSMENT</span>
                    <h2>Grounded decision</h2>
                  </div>
                  <span className={`status large ${detail?.decision.status ?? ""}`}>
                    {detail ? statusLabel(detail.decision.status) : "—"}
                  </span>
                </div>

                <div className="assessment-body">
                  <div className="score-card">
                    <div className="confidence-ring" style={{ "--score": (detail?.decision.confidence ?? 0) * 100 } as React.CSSProperties}>
                      <strong>{detail ? Math.round(detail.decision.confidence * 100) : "—"}</strong>
                      <span>CONFIDENCE</span>
                    </div>
                    <div className="score-facts">
                      <div><span>BASELINE SCORE</span><strong>{detail?.baseline.score ?? "—"} / 100</strong></div>
                      <div><span>GROUNDING</span><strong className={detail?.decision.grounded ? "ok" : "warn"}>{detail?.decision.grounded ? "VALID" : "REVIEW"}</strong></div>
                      <div><span>CITATIONS</span><strong>{citedCount} / {detail?.retrieval.sources.length ?? 0}</strong></div>
                    </div>
                  </div>

                  <div className="reasoning">
                    <span className="subhead">REASONING</span>
                    <p>{detail?.decision.reasoning ?? "—"}</p>
                    {detail?.decision.exception && (
                      <div className="exception">
                        <span>EXCEPTION DETECTED</span>
                        <p>{detail.decision.exception}</p>
                      </div>
                    )}
                    {!!detail?.decision.missing_evidence.length && (
                      <div className="missing">
                        <span>MISSING EVIDENCE</span>
                        <ul>{detail.decision.missing_evidence.map((item) => <li key={item}>{item}</li>)}</ul>
                      </div>
                    )}
                  </div>
                </div>
              </section>

              <section className="panel checks-panel">
                <div className="panel-head">
                  <div>
                    <span className="eyebrow">DETERMINISTIC GUARDRAILS</span>
                    <h2>Evidence coverage checks</h2>
                  </div>
                  <span className="baseline-tag">BASELINE {detail?.baseline.score ?? "—"}</span>
                </div>
                <div className="checks-grid">
                  {coverageItems.map((item) => (
                    <div className="check" key={item.label}>
                      <span className={item.pass ? "pass" : "fail"}>{item.pass ? "✓" : "!"}</span>
                      <div><small>{item.label}</small><strong>{item.value}</strong></div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="panel retrieval-panel">
                <div className="panel-head">
                  <div>
                    <span className="eyebrow">RAG RETRIEVAL</span>
                    <h2>Retrieved sources & citations</h2>
                  </div>
                  <span className="grounding-tag">{detail?.validation.grounded ? "✓ GROUNDED" : "⚠ REVIEW"}</span>
                </div>
                <div className="retrieval-query">
                  <span>QUERY</span>
                  <p>{detail?.retrieval.query ?? "—"}</p>
                </div>
                <div className="retrieval-layout">
                  <div className="source-list">
                    {detail?.retrieval.sources.map((source, index) => (
                      <button
                        key={source.source_id}
                        className={`source-row ${selectedSource?.source_id === source.source_id ? "active" : ""}`}
                        onClick={() => setSelectedSource(source)}
                      >
                        <span className="rank">{String(index + 1).padStart(2, "0")}</span>
                        <div>
                          <strong>{source.source_id}</strong>
                          <small>{source.document_type}</small>
                        </div>
                        <div className="retrieval-score">
                          <span>{Math.round(source.score * 100)}</span>
                          <i style={{ width: `${Math.max(6, source.score * 100)}%` }} />
                        </div>
                        {source.cited && <span className="cited">CITED</span>}
                      </button>
                    ))}
                  </div>
                  <div className="source-preview">
                    <div className="source-preview-head">
                      <span>{selectedSource?.document_type ?? "SOURCE"}</span>
                      <strong>{selectedSource?.source_id ?? "Select a source"}</strong>
                    </div>
                    <pre>{selectedSource?.text ?? "Select a retrieved source to inspect the exact grounded context."}</pre>
                  </div>
                </div>
              </section>
            </div>

            <aside className="right-stack">
              <section className="panel evidence-card">
                <div className="panel-head">
                  <div>
                    <span className="eyebrow">PRIMARY EVIDENCE</span>
                    <h2>{evidence?.evidence_id ?? "No evidence"}</h2>
                  </div>
                  <span className="file-icon">TXT</span>
                </div>
                {evidence ? (
                  <>
                    <div className="evidence-meta">
                      <div><span>FILE</span><strong>{evidence.filename}</strong></div>
                      <div><span>OWNER</span><strong>{evidence.owner}</strong></div>
                      <div><span>PERIOD</span><strong>{evidence.period}</strong></div>
                      <div><span>TYPE</span><strong>{evidence.evidence_type}</strong></div>
                    </div>
                    <div className="evidence-preview">
                      <span>DOCUMENT PREVIEW</span>
                      <pre>{evidence.text}</pre>
                    </div>
                  </>
                ) : (
                  <div className="no-evidence">
                    <strong>NO MATCHING EVIDENCE</strong>
                    <p>The agent cannot replace missing evidence with unrelated retrieved content.</p>
                  </div>
                )}
              </section>

              <section className="panel review-panel">
                <div className="panel-head">
                  <div>
                    <span className="eyebrow">HUMAN-IN-THE-LOOP</span>
                    <h2>Reviewer decision</h2>
                  </div>
                  <span className={`review-state ${detail?.review.status ?? "pending"}`}>
                    {detail?.review.status === "completed" ? "RECORDED" : "PENDING"}
                  </span>
                </div>

                {detail?.review.status === "completed" && (
                  <div className="review-recorded">
                    <span>LAST DECISION</span>
                    <strong>{detail.review.decision?.replace("_", " ").toUpperCase()}</strong>
                    <small>{detail.review.timestamp ? new Date(detail.review.timestamp).toLocaleString() : ""}</small>
                  </div>
                )}

                <label className="feedback-field">
                  <span>REVIEWER FEEDBACK</span>
                  <textarea
                    value={feedback}
                    onChange={(event) => setFeedback(event.target.value)}
                    placeholder="Add review rationale or requested follow-up…"
                  />
                </label>

                <div className="review-actions">
                  <button disabled={reviewing} className="approve" onClick={() => void submitReview("approve")}>✓ APPROVE</button>
                  <button disabled={reviewing} className="changes" onClick={() => void submitReview("needs_changes")}>↻ NEEDS CHANGES</button>
                  <button disabled={reviewing} className="reject" onClick={() => void submitReview("reject")}>× REJECT</button>
                </div>
                <p className="ephemeral-note">Demo review state is ephemeral and resets when the free backend restarts.</p>
              </section>

              <section className="panel trace-panel">
                <div className="panel-head">
                  <div>
                    <span className="eyebrow">TRACEABILITY</span>
                    <h2>Decision lineage</h2>
                  </div>
                  <span className="run-id">{truncate(detail?.trace.run_id ?? "—", 22)}</span>
                </div>
                <div className="trace-steps">
                  {detail?.trace.steps.map((step) => (
                    <div className={`trace-step ${step.state}`} key={step.id}>
                      <span className="trace-index">{step.id}</span>
                      <i />
                      <div><strong>{step.name}</strong><small>{step.detail}</small></div>
                    </div>
                  ))}
                </div>
              </section>
            </aside>
          </section>
        </main>
      </div>

      <footer>
        <span>CONTROL//ROOM · PUBLIC-SAFE PORTFOLIO DEMO</span>
        <span>Deterministic guardrails + TF-IDF RAG + heuristic agent + HITL + evaluation</span>
        <span>Not an audit opinion or compliance certification</span>
      </footer>
    </div>
  );
}

export default App;
