import { useState } from 'react';
import { operations } from './client';
import type { Session } from './types';
import Operations from './Operations';

// Read once before React StrictMode renders, then erase the bearer capability from the URL.
const parameters = new URLSearchParams(location.hash.slice(1));
const initialToken = parameters.get('invite');
export const hasInvitation = initialToken !== null || location.hash === '#invitation';
if (initialToken !== null) history.replaceState(null, '', `${location.pathname}${location.search}#invitation`);

export default function Invitation() {
  const [session, setSession] = useState<Session>();
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  if (session) return <Operations externalSession={session}/>;
  return <main className="ops-invite-page"><section className="ops-card"><span className="ops-eyebrow">EVIDENCE / EXTERNAL CONTRIBUTOR</span><h1>Review invitation</h1><p>Accept to view one assigned request and submit evidence. You cannot approve records. This public demo uses fictional data.</p><p>Your session stays in this tab. Reloading requires a new invitation.</p>{error && <p role="alert">{error}</p>}<label>Your name<input aria-label="Your name" value={name} maxLength={120} onChange={e => setName(e.target.value)}/></label><button className="ops-primary" disabled={busy || !name.trim() || !initialToken} onClick={() => { setBusy(true); setError(''); void operations.accept(initialToken!, name).then(setSession).catch(e => setError(e.message)).finally(() => setBusy(false)); }}>Accept invitation</button>{!initialToken && <p>This invitation is unavailable. Ask your reviewer for a new link.</p>}</section></main>;
}
