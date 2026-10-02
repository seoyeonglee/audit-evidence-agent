import { useEffect, useRef, useState } from 'react';
import { operations } from './client';
import type { Metrics, RecordDetail, RequestSummary, Session } from './types';
import './operations.css';

const PERSONAS = [ ['reviewer','Reviewer · Maya Chen'], ['auditor','Auditor · Elliot Park'], ['owner','Control owner · Alex Rivera'], ['vendor','External vendor · Jordan Vale'], ['other-reviewer','Other organization · Nora Kim'] ];
const SAMPLE = 'system: production-admin\nperiod: 2026-Q3\nreviewed_users: 84\nexceptions: 0\nowner: Security Team';
const short = (value: string) => value.slice(0, 12);
const label = (value: string) => value.replaceAll('_', ' ').toUpperCase();

export default function Operations() {
  const [persona, setPersona] = useState('reviewer');
  const [session, setSession] = useState<Session | null>(null);
  const [requests, setRequests] = useState<RequestSummary[]>([]);
  const [detail, setDetail] = useState<RecordDetail | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [reports, setReports] = useState<Record<string, any>>({});
  const [verified, setVerified] = useState(false);
  const [content, setContent] = useState(SAMPLE);
  const [feedback, setFeedback] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);

  async function refresh(user: Session, selected?: string) {
    const [list, stats, measured] = await Promise.all([operations.requests(user.token), operations.metrics(user.token), operations.measurements(user.token)]);
    const id = list.requests.find(r => r.id === selected)?.id ?? list.requests[0]?.id;
    const record = id ? await operations.detail(user.token, id) : null;
    const history = id ? await operations.verify(user.token, id) : null;
    return { list, stats, measured, record, history };
  }
  function apply(data: Awaited<ReturnType<typeof refresh>>) {
    setRequests(data.list.requests); setMetrics(data.stats); setReports(data.measured.reports);
    setDetail(data.record); setVerified(data.history?.valid ?? false);
  }
  useEffect(() => {
    const current = ++generation.current;
    setSession(null); setDetail(null); setRequests([]); setMetrics(null); setError(''); setNotice(''); setBusy(true);
    void (async () => {
      try {
        const user = await operations.session(persona);
        const data = await refresh(user);
        if (generation.current !== current) return;
        setSession(user); apply(data);
      } catch (err) { if (generation.current === current) setError(err instanceof Error ? err.message : 'Connection unavailable'); }
      finally { if (generation.current === current) setBusy(false); }
    })();
    return () => { generation.current++; };
  }, [persona]);

  async function action(fn: (user: Session, record: RecordDetail) => Promise<string>) {
    if (!session || !detail || busy) return;
    const current = generation.current;
    setBusy(true); setError(''); setNotice('');
    try {
      const message = await fn(session, detail);
      const data = await refresh(session, detail.id);
      if (current !== generation.current) return;
      apply(data); setNotice(message);
    } catch (err) { if (current === generation.current) setError(err instanceof Error ? err.message : 'Action failed'); }
    finally { if (current === generation.current) setBusy(false); }
  }
  async function choose(id: string) {
    if (!session || busy) return;
    const current = generation.current; setBusy(true); setError('');
    try {
      const [record, history] = await Promise.all([operations.detail(session.token, id), operations.verify(session.token, id)]);
      if (current !== generation.current) return;
      setDetail(record); setVerified(history.valid); setFeedback(''); setNotice('');
    } catch (err) { if (current === generation.current) setError(err instanceof Error ? err.message : 'Load failed'); }
    finally { if (current === generation.current) setBusy(false); }
  }

  const fields = Object.entries(detail?.canonical.fields ?? {});
  const exceptions = detail?.canonical.exceptions ?? [];
  const canSubmit = !!session && session.role !== 'reviewer' && detail?.status !== 'approved';
  const canReview = session?.role === 'reviewer';
  const evaluation = reports.evaluation;
  const benchmark = reports.benchmark;
  return <div className="ops-shell">
    <header className="ops-topbar">
      <div className="ops-brand"><span className="ops-mark">EO</span><div><strong>EVIDENCE / OPS</strong><small>Auditable work. Verifiable outcomes.</small></div></div>
      <div className="ops-session"><span className="ops-demo">SYNTHETIC WORKSPACE</span><label>Demo persona<select aria-label="Demo persona" value={persona} onChange={e => setPersona(e.target.value)}>{PERSONAS.map(([id,name]) => <option value={id} key={id}>{name}</option>)}</select></label></div>
    </header>
    <section className="ops-hero">
      <div><span className="ops-eyebrow">EVIDENCE OPERATIONS PLATFORM / V3</span><h1>Evidence operations</h1><p>From scattered documents to a single, source-backed record.<br/>Every field has a source. Every decision has an owner.</p></div>
      <div className="ops-identity"><span className="ops-live"><i/> {session ? 'CONNECTED' : 'CONNECTING'}</span><strong>{session?.name ?? 'Opening workspace…'}</strong><span>{session?.tenant_id ?? '—'} / {session?.role ?? '—'}</span><small>Tenant identity is resolved from the server token.</small></div>
    </section>
    <div className="ops-kpis">
      <div><span>VISIBLE REQUESTS</span><strong>{metrics?.requests ?? '—'}<small>scoped by membership</small></strong></div>
      <div><span>DURABLE JOBS</span><strong>{metrics?.jobs ?? '—'}<small>{metrics?.queue.succeeded ?? 0} processed · {metrics?.queue.queued ?? 0} queued</small></strong></div>
      <div><span>REVIEWED RECORDS</span><strong>{metrics?.approved ?? '—'}<small>human approval required</small></strong></div>
      <div className="ops-kpi-accent"><span>AUDIT CHAIN</span><strong>{verified ? 'Verified' : '—'}<small>{detail?.events.length ?? 0} append-only events</small></strong></div>
    </div>
    {(error || notice) && <div role="status" className={`ops-notice ${error ? 'ops-error' : ''}`}>{error || notice}</div>}
    <main className="ops-layout">
      <aside className="ops-requests ops-card">
        <div className="ops-card-heading"><span className="ops-eyebrow">WORKSPACE</span><h2>Evidence requests</h2><span className="ops-muted">2026 Q3 / {requests.length} visible</span></div>
        <div className="ops-request-list">{requests.map(r => <button aria-label={`${r.id} ${r.title}`} disabled={busy} key={r.id} onClick={() => void choose(r.id)} className={`ops-request ${detail?.id === r.id ? 'is-selected' : ''}`}><span className="ops-request-id">{r.control_id}<span className={`ops-dot ${r.status}`}/></span><strong>{r.title}</strong><span className={`ops-badge ${r.status}`}>{label(r.status)}</span><small>{r.id} · version {r.version}</small></button>)}</div>
        <div className="ops-boundary"><span>↳ ACCESS BOUNDARY</span><p>Owners and vendors see assigned requests. Reviewers approve. Organizations remain isolated.</p><small>RLS verified in PostgreSQL CI profile</small></div>
      </aside>
      <section className="ops-record">
        <article className="ops-card">
          <div className="ops-record-head"><div><span className="ops-eyebrow">CANONICAL EVIDENCE RECORD</span><h2>{detail?.title ?? 'Loading evidence record'}</h2><small>{detail?.id ?? '—'} · {detail?.period ?? '—'} · version {detail?.version ?? 0}</small></div><span data-testid="request-status" className={`ops-badge ${detail?.status}`}>{label(detail?.status ?? 'loading')}</span></div>
          <div className="ops-facts-heading"><span>EXTRACTED FACT</span><span>SOURCE / LINEAGE</span></div>
          <div className="ops-facts">{fields.length ? fields.map(([key, fact]) => <div className="ops-fact" key={key}><div><small>{label(key)}</small><strong>{String(fact.value)}</strong></div><div><span className="ops-source-ok">✓ Source verified</span><code>{short(fact.source.document_id)} / L{fact.source.line}</code><blockquote>{fact.source.quote}</blockquote></div></div>) : <div className="ops-empty"><span>◇</span><h3>Waiting for source evidence</h3><p>Switch to Control owner to submit a sample.<br/>Then return as Reviewer to process and inspect it.</p></div>}</div>
          {exceptions.length > 0 && <div className="ops-exceptions">{exceptions.map((e, i) => <div key={i}><strong>{e.code}</strong><p>{e.message}</p></div>)}</div>}
          <div className="ops-record-footer"><span>STRUCTURED EXTRACTION + SCHEMA VALIDATION</span><span>{detail?.canonical.complete ? '✓ Complete & exception-free' : 'Human verification pending'}</span></div>
        </article>
        {canSubmit && <article className="ops-card ops-intake"><div className="ops-card-heading"><span className="ops-eyebrow">EVIDENCE INTAKE</span><h2>Submit source evidence</h2><p>Sample data only. The submission creates a persisted document and queued job atomically.</p></div><textarea aria-label="Evidence content" value={content} onChange={e => setContent(e.target.value)} rows={5}/><div className="ops-intake-actions"><label className="ops-file">Choose text file<input type="file" accept=".txt" onChange={e => { const file = e.target.files?.[0]; if (file) { if (file.size > 200000) setError('Text file exceeds 200KB'); else void file.text().then(setContent); } }}/></label><button className="ops-primary" disabled={busy || !content.trim()} onClick={() => void action(async (u,r) => { await operations.submit(u.token,r.id,content); return 'Evidence accepted. A durable processing job was queued.'; })}>Submit sample evidence</button></div></article>}
        {canReview && <article className="ops-card ops-review"><div className="ops-card-heading"><span className="ops-eyebrow">HUMAN IN THE LOOP</span><h2>Review & sign off</h2><p>Approval checks record version, source sufficiency and separation of duties.</p></div><textarea aria-label="Reviewer feedback" placeholder="Document your review rationale…" value={feedback} onChange={e => setFeedback(e.target.value)} rows={2}/><div className="ops-review-actions">{[['approve','Approve record'],['needs_changes','Request changes'],['reject','Reject record']].map(([decision,text]) => <button key={decision} className={decision === 'approve' ? 'ops-primary' : 'ops-secondary'} disabled={busy || detail?.status === 'approved' || ['processing','awaiting_evidence'].includes(detail?.status ?? '') || (decision === 'approve' && !detail?.canonical.complete)} onClick={() => void action(async (u,r) => { const reviewed = await operations.review(u.token,r.id,r.version,decision,feedback); return `Review recorded: ${reviewed.status}.`; })}>{text}</button>)}</div></article>}
        <article className="ops-card ops-timeline"><div className="ops-card-heading"><span className="ops-eyebrow">TRACEABILITY</span><h2>Decision timeline</h2><span className="ops-muted">Append-only event log · SHA-256 chain</span></div>{detail?.events.length ? detail.events.map(e => <div className="ops-event" key={e.id}><span className="ops-event-node"/><div><strong>{e.event_type}</strong><small>{e.actor} · {new Date(e.created_at).toLocaleTimeString('en-US', { hour12: false })}</small><code>{short(e.event_hash)}…</code></div></div>) : <p className="ops-muted ops-no-events">Events appear when evidence is submitted and reviewed.</p>}</article>
      </section>
      <aside className="ops-system">
        <article className="ops-card"><div className="ops-card-heading"><span className="ops-eyebrow">PROCESSING</span><h2>Durable job pipeline</h2></div><div className="ops-pipeline">{['Submit & persist','Lease worker job','Extract source facts','Validate canonical record','Human review'].map((step,i) => <div key={step}><span className={i === 4 ? 'ops-stage-human' : ''}>{String(i+1).padStart(2,'0')}</span><div><strong>{step}</strong><small>{['Atomic document + job transaction','Expiring lease / retry / dead letter','Field value + document digest + quote','Period, counts, missing data & conflict checks','Version guard / immutable approved record'][i]}</small></div></div>)}</div>{canReview && <button className="ops-process" disabled={busy} onClick={() => void action(async u => { const result = await operations.process(u.token); return `${result.processed} queued document(s) processed.`; })}>Process queued documents <span>→</span></button>}<p className="ops-footnote">Demo runs bounded worker ticks. Deployment runs the worker as an independent process.</p></article>
        <article className="ops-card"><div className="ops-card-heading"><span className="ops-eyebrow">QUEUE OBSERVABILITY</span><h2>Job state</h2></div><div className="ops-job-counts">{['queued','running','succeeded','dead_letter'].map(s => <div key={s}><span>{label(s)}</span><strong>{metrics?.queue[s] ?? 0}</strong><div className={`ops-bar ${s}`} style={{ width: `${Math.min(100, (metrics?.queue[s] ?? 0) / Math.max(1, metrics?.jobs ?? 1) * 100)}%` }}/></div>)}</div><div className="ops-stat-row"><span>Retry attempts</span><strong>{metrics?.retry_attempts ?? 0}</strong></div><div className="ops-stat-row"><span>Storage backend</span><strong>{metrics?.storage ?? '—'}</strong></div><div className="ops-job-list">{detail?.jobs.map(j => <div key={j.id}><code>{short(j.id)}</code><span className={`ops-badge ${j.status}`}>{label(j.status)}</span><small>Attempt {j.attempts}{j.error ? ` · ${j.error}` : ''}</small></div>)}</div></article>
        <article className="ops-card ops-measured"><div className="ops-card-heading"><span className="ops-eyebrow">REPRODUCIBLE MEASUREMENTS</span><h2>Evidence, not estimates</h2></div><div className="ops-stat-row"><span>Offline evaluation</span><strong>{evaluation ? `${evaluation.cases} cases` : 'Pending report'}</strong></div><div className="ops-stat-row"><span>Field exact match</span><strong>{evaluation ? `${(evaluation.field_exact_match * 100).toFixed(1)}%` : '—'}</strong></div><div className="ops-stat-row"><span>Measured read p95</span><strong>{benchmark ? `${benchmark.read_p95_ms.toFixed(2)} ms` : '—'}</strong></div><p className="ops-footnote">Checked-in local synthetic runs. Offline extraction rules; these are not LLM or cloud performance scores.</p><a href="https://github.com/seoyeonglee/audit-evidence-agent/tree/main/docs/reports" target="_blank" rel="noreferrer">Inspect raw reports ↗</a></article>
      </aside>
    </main>
    <footer className="ops-footer"><span>DOCUMENTS → STRUCTURED FACTS → VALIDATION → HUMAN DECISION → AUDIT TRAIL</span><span>Synthetic reference system / {busy ? 'Working…' : 'Ready'}</span></footer>
  </div>;
}
