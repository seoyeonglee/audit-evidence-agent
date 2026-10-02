import { useState } from 'react';
import App from './App';
import Operations from './operations/Operations';
export default function Workspace() {
  const [view, setView] = useState('operations');
  return <><nav className="workspace-tabs"><span>AUDIT EVIDENCE / ENGINEERING REFERENCE</span><div><button className={view === 'operations' ? 'active' : ''} onClick={() => setView('operations')}>Operations</button><button className={view === 'rag' ? 'active' : ''} onClick={() => setView('rag')}>RAG Lab</button><a href="https://github.com/seoyeonglee/audit-evidence-agent" target="_blank" rel="noreferrer">GitHub ↗</a></div></nav>{view === 'operations' ? <Operations /> : <App />}</>;
}
