import { useEffect, useState } from 'react';
import { api } from '../api';
import './cloud.css';

type Mapping = { framework: string; domain: string; relationship: string; source: string; rationale: string };
type Result = { id: string; title: string; domain: string; owner: string; priority: string; status: string; reason: string; next_action: string; scope_limit: string; responsibility: string; technical_source: string; mappings: Mapping[]; evidence_sha256: string | null; evidence: { source: string; collected_at: string; resource: string; data: unknown } | null; checks_observed: { path: string; expected: unknown; actual: unknown; status: string }[] };
type Report = { as_of: string; account_id: string; region: string; summary: Record<string, number>; results: Result[]; catalog_version: string };
const labels: Record<string, string> = { ready_for_review: 'Ready for review', gap: 'Configuration gap', stale: 'Stale evidence', missing: 'Missing evidence', manual_review: 'Manual review', out_of_scope: 'Out of scope', invalid: 'Invalid date' };
async function call(path: string, payload?: unknown) {
  const response = await fetch(api.baseUrl + '/api/cloud-assurance/' + path, payload === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.detail || `API unavailable (${response.status}). Try again after the service wakes up.`); }
  return response.json();
}

export default function CloudAssurance() {
  const [report, setReport] = useState<Report | null>(null);
  const [editor, setEditor] = useState('');
  const [selected, setSelected] = useState('CC-STORAGE');
  const [filter, setFilter] = useState('all');
  const [framework, setFramework] = useState('all');
  const [open, setOpen] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  async function loadSample() {
    setBusy(true); setError(''); setReport(null);
    try { const sample = await call('sample'); setEditor(JSON.stringify(sample, null, 2)); setReport(await call('assess', sample)); setDirty(false); }
    catch (e) { setError(e instanceof Error ? e.message : 'Unable to load sample.'); }
    finally { setBusy(false); }
  }
  useEffect(() => { void loadSample(); }, []);
  async function run() {
    setBusy(true); setError(''); setReport(null);
    try {
      let parsed; try { parsed = JSON.parse(editor); } catch { throw new Error('Invalid JSON. Check the evidence bundle and try again.'); }
      setReport(await call('assess', parsed)); setDirty(false);
    } catch (e) { setError(e instanceof Error ? e.message : 'Assessment failed.'); }
    finally { setBusy(false); }
  }
  function download() {
    if (!report || dirty) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
    const a = document.createElement('a'); a.href = url; a.download = 'cloud-assurance-review.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const visible = report?.results.filter(r => filter === 'all' || r.status === filter) ?? [];
  const current = visible.find(r => r.id === selected) ?? visible[0];
  return <main className="cloud-shell">
    <header className="cloud-hero"><div><div className="cloud-eyebrow"><i /> EVIDENCE OPERATIONS / CLOUD ASSURANCE</div><h1>Cloud assurance,<br />grounded in evidence.</h1><p>One control objective. Multiple frameworks. An inspectable path from cloud settings to the next review action.</p></div><aside><span className="cloud-demo">SYNTHETIC WORKSPACE</span><dl><dt>Assessment date</dt><dd>{report?.as_of ?? '2026-10-06'}</dd><dt>Scope</dt><dd>{report?.account_id ?? 'demo-account'}<br />{report?.region ?? 'ap-northeast-2'}</dd><dt>Decision boundary</dt><dd>Readiness · human review required</dd></dl></aside></header>
    <div className="cloud-toolbar"><div><button onClick={() => setOpen(!open)} aria-expanded={open}>Edit evidence bundle</button><button onClick={loadSample} disabled={busy}>Reset sample</button></div><button className="cloud-primary" onClick={download} disabled={!report || dirty || busy}>Export review pack <span aria-hidden="true">↗</span></button></div>
    {open && <section className="cloud-editor"><h2>Explore a different evidence state</h2><p>Use synthetic data only. Change a flag, collection date or account, then rerun. The API processes the bundle without storing it.</p><label htmlFor="cloud-json">Synthetic evidence JSON</label><textarea id="cloud-json" value={editor} disabled={busy} onChange={e => { setEditor(e.target.value); setDirty(true); }} spellCheck={false} /><button className="cloud-primary" onClick={run} disabled={busy}>Run readiness checks</button>{dirty && <span> Evidence changed · rerun to export current results.</span>}</section>}
    {error && <p className="cloud-error" role="alert">{error}</p>}
    {busy && <p role="status">Inspecting evidence and control requirements…</p>}
    {report && <>
      {dirty && <p className="cloud-notice">The results below describe the previous bundle. Run readiness checks to refresh.</p>}
      <section className="cloud-metrics" aria-label="Readiness summary"><div><small>CONTROL OBJECTIVES</small><strong>{report.results.length.toString().padStart(2, '0')}</strong><span>4 automated · 4 manual</span></div><div><small>READY FOR REVIEW</small><strong>{report.summary.ready_for_review ?? 0}</strong><span>Configuration checks matched</span></div><div><small>EVIDENCE ACTIONS</small><strong>{Object.entries(report.summary).filter(([key]) => !['ready_for_review','manual_review'].includes(key)).reduce((n, [,v]) => n+v,0)}</strong><span>Gaps, missing or invalid evidence</span></div><div><small>HUMAN REVIEW</small><strong>{report.summary.manual_review ?? 0}</strong><span>Documents need assessment</span></div></section>
      <section className="cloud-grid"><aside className="cloud-controls"><div className="cloud-section-label">01 / CONTROL REGISTER</div><label htmlFor="cloud-filter">Readiness filter</label><select id="cloud-filter" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All control objectives</option>{Object.keys(report.summary).map(s => <option key={s} value={s}>{labels[s]}</option>)}</select><div className="cloud-control-list">{visible.map(r => <button key={r.id} className={current?.id === r.id ? 'selected' : ''} onClick={() => setSelected(r.id)}><small>{r.id} / {r.domain}</small><strong>{r.title}</strong><span className={'cloud-status ' + r.status}>{labels[r.status]}</span></button>)}</div></aside>
      {current ? <article className="cloud-detail"><div className="cloud-section-label">02 / EVIDENCE & REVIEW</div><div className="cloud-detail-title"><h2>{current.title}</h2><span className={'cloud-status ' + current.status}>{labels[current.status]}</span></div><p>{current.reason}</p><div className="cloud-facts"><div><small>RECOMMENDED OWNER</small><b>{current.owner}</b></div><div><small>PRIORITY</small><b>{current.priority.toUpperCase()}</b></div><div><small>RESPONSIBILITY</small><span>{current.responsibility}</span></div></div>
        <h3>Observed configuration</h3>{current.checks_observed.length ? <div className="cloud-table-wrap"><table><thead><tr><th>Evidence field</th><th>Observed</th><th>Expected</th><th>Result</th></tr></thead><tbody>{current.checks_observed.map(c => <tr key={c.path}><td><code>{c.path}</code></td><td>{JSON.stringify(c.actual)}</td><td>{JSON.stringify(c.expected)}</td><td className={'cloud-cell-' + c.status}>{c.status}</td></tr>)}</tbody></table></div> : <p className="cloud-muted">{current.evidence ? 'No automated verdict. Review the source material below.' : 'No evidence supplied for this control.'}</p>}
        <div className="cloud-next"><small>NEXT ACTION</small><p>{current.next_action}</p></div><p className="cloud-limit"><b>Scope limit.</b> {current.scope_limit} <a href={current.technical_source} target="_blank" rel="noreferrer">Technical reference ↗</a></p>
        <div className="cloud-mapping-title"><h3>Common control crosswalk</h3><select aria-label="Framework filter" value={framework} onChange={e => setFramework(e.target.value)}><option value="all">All frameworks</option>{current.mappings.map(m => <option key={m.framework}>{m.framework}</option>)}</select></div><p className="cloud-muted">Authored domain overlaps · candidate mappings, not verified equivalence. Validate current criteria and scope before audit use.</p><div className="cloud-mappings">{current.mappings.filter(m => framework === 'all' || framework === m.framework).map(m => <div key={m.framework}><a href={m.source} target="_blank" rel="noreferrer">{m.framework} ↗</a><span>{m.domain}</span><small>Candidate · reviewer validation needed</small></div>)}</div>
        <details className="cloud-source"><summary>Inspect source & content fingerprint</summary>{current.evidence ? <><p>{current.evidence.source}<br />Resource: {current.evidence.resource} · Collected: {current.evidence.collected_at}</p><pre>{JSON.stringify(current.evidence.data, null, 2)}</pre><small>SHA-256 · identifies submitted content, not collector authenticity</small><code>{current.evidence_sha256}</code></> : <p>No source available.</p>}</details>
      </article> : <p>No controls match this filter.</p>}</section>
    </>}
    <footer className="cloud-footer"><span>Readiness is a starting point, not a certification outcome.</span><span>CSAP ≠ financial-sector CSP Safety · catalog {report?.catalog_version ?? '2026-10-06.1'}</span><a href="https://github.com/seoyeonglee/audit-evidence-agent/blob/main/docs/cloud-assurance.md" target="_blank" rel="noreferrer">Methodology & limits ↗</a></footer>
  </main>;
}
