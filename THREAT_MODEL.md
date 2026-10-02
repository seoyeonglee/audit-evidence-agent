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
