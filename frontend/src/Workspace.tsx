import { useEffect, useState } from 'react';
import App from './App';
import CloudAssurance from './cloud/CloudAssurance';
import Operations from './operations/Operations';
import Invitation, { hasInvitation } from './operations/Invitation';
export default function Workspace() {
  const [view, setView] = useState(location.hash === '#cloud' ? 'cloud' : location.hash === '#rag' ? 'rag' : 'operations');
  useEffect(() => { const sync = () => setView(location.hash === '#cloud' ? 'cloud' : location.hash === '#rag' ? 'rag' : 'operations'); window.addEventListener('hashchange', sync); return () => window.removeEventListener('hashchange', sync); }, []);
  if (hasInvitation) return <Invitation />;
  return <><nav className="workspace-tabs"><span>AUDIT EVIDENCE / ENGINEERING REFERENCE</span><div><button className={view === 'operations' ? 'active' : ''} onClick={() => { setView('operations'); history.replaceState(null, '', '#operations'); }}>Operations</button><button className={view === 'rag' ? 'active' : ''} onClick={() => { setView('rag'); history.replaceState(null, '', '#rag'); }}>RAG Lab</button><button className={view === 'cloud' ? 'active' : ''} onClick={() => { setView('cloud'); history.replaceState(null, '', '#cloud'); }}>Cloud Assurance</button><a href="https://github.com/seoyeonglee/audit-evidence-agent" target="_blank" rel="noreferrer">GitHub ↗</a></div></nav>{view === 'cloud' ? <CloudAssurance /> : view === 'operations' ? <Operations /> : <App />}</>;
}
