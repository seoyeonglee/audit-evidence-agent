# Threat model

Assets: source evidence, extracted facts, reviewer decisions, tenant membership, processing state and audit lineage. Trust boundaries: browser→API, token→membership, tenant→database, uploaded content→extractor, worker→canonical record, reviewer→approved state.

| Threat | Implemented defense | Verification / residual risk |
|---|---|---|
| Cross-tenant reads and writes | Server token identity, explicit tenant filters, composite foreign keys, PostgreSQL FORCE RLS | Direct unfiltered SQL, cross-tenant INSERT and pooled-context tests; migration owner must stay separate |
| Assigned vendor reads unrelated records | Owner/vendor assignment predicates on list/detail/submit | Role and request-scope tests; runtime DB credential is a trusted server credential |
| Privilege escalation through headers | No caller-supplied tenant/role authority | API test supplies a conflicting X-Tenant-ID |
| Self approval or stale approval | Reviewer membership, independent submitter, optimistic version | Non-reviewer and stale-version tests; actual organization onboarding is not implemented |
| Prompt instructions in evidence | Explicit quarantine for recognizable instruction-like text; evidence cannot issue actions | Adverse fixtures; regex is not a comprehensive prompt-injection detector |
| Unsupported or malformed uploaded facts | Typed scalars, calendar parsing, known field whitelist, bounded content | Invalid counts/dates/duplicate fields; free-form extraction is deliberately rejected |
| Invented source verification | Exact source span/line/digest for supported parsers | Pretty-JSON padding regression; semantic entailment is not implied |
| Malicious files | Text intake only, filename/path limits, bounded length; PDF helper rejects encryption/scan-only content | Binary upload endpoint and malware scanner are not provided |
| Duplicate webhooks | Tenant-wide unique key + payload fingerprint + PostgreSQL advisory lock | Identical replay returns original job; changed payload returns 409 |
| Worker crash / stale callback | Expiring lease, token fencing, capped attempts, dead letter, consistent lock order | Crash/reclaim and PostgreSQL concurrency schedules |
| Audit rewriting | UPDATE/DELETE triggers, append-only events, SHA-256 chain | Direct SQL mutation tests; DB administrator can disable triggers/rewrite entire chain |
| Secret leakage | Random opaque tokens, hashed token storage, error type only | Retry test checks uploaded/exception secret text is absent from record output |
| Public demo used for private evidence | DEMO_MODE explicit opt-in; fixed fictional personas | Absent opt-in regression; demo is public and single API process only |

## Before private production use

Provision SSO or a token rotation/revocation workflow; separate migration/runtime credentials; configure storage encryption and retention according to actual needs; add rate limits and upload malware scanning; externalize binary objects with scoped signed URLs; send audit-chain heads to an independent immutable sink; implement supervised correction/supersession. TLS is provided by the hosting profile, but this repository does not claim encrypted local SQLite or deployed WORM storage.

## Enterprise graph and desktop additions

Agent identity comes from authenticated membership; run/thread IDs and checkpoint paths are server-owned. New SQL tables use tenant RLS, composite tenant foreign keys and append-only command/event triggers. Exact source checks validate digest, quote, line and citation identifiers; this proves provenance, not semantic compliance. Heuristic evidence assessment cannot execute tools or change roles.

Graph checkpoint files contain frozen evidence and require a private one-host directory. SQLite file locks exclude concurrent graph writers; SQL leases fence registry writes. Production provisioning must migrate and grant the new tables under a non-bypass runtime role. The demo uses synthetic local SQLite only.

Electron main owns files, dialogs and the loopback sidecar secret. Renderer routes/bodies/senders are bounded and allowlisted. An unexpected local client without the transport secret is rejected even before membership checks. The preload does not expose paths, arbitrary IPC or Node APIs. Local source files must be regular, non-symlink UTF-8 with separate byte and character limits. A renderer compromise can invoke its allowed operations and access its synthetic session; this is a reference architecture, not protection against a compromised OS account.

Linux runtime captures are real Electron executions under Xvfb with --no-sandbox in a root environment. They do not establish OS sandbox enforcement, signed distribution security or Windows/macOS runtime behavior.
