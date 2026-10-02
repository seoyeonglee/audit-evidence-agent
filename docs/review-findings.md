# Independent code review and verification

The workflow was reviewed by a separate code-review agent; this is automated review, not an external human endorsement. The review found no Critical issues and identified five Important defects plus a PostgreSQL migration failure from the actual CI job.

| Finding | Change | Evidence |
|---|---|---|
| Tenant-wide idempotency locked only one request | PostgreSQL transaction advisory lock covers tenant/key before request lock | Concurrent different-request reuse must yield one success and one 409 |
| Lease recovery used a different lock order | Finalize/fail now lock job→request consistently with recovery | Coordinated PostgreSQL expired-lease/stale-completion test |
| Invalid calendar dates passed formatting checks | `date.fromisoformat` validates actual dates | Two invalid dates observed failing before fix, then passing |
| JSON quote/line could reference unrelated padding | Capture each recognized JSON field's exact source span and line | Pretty JSON with 600-character preceding property regression |
| Public demo defaulted on without explicit setting | Missing DEMO_MODE defaults closed; launch/demo service explicitly sets 1 | Absent-opt-in test observed failing before fix, then passing |
| psycopg interpreted PL/pgSQL `%I` as a DBAPI placeholder | Execute migration through SQLAlchemy `text()` | First PostgreSQL CI run failed before policy tests; [Follow-up CI passed all 11 PostgreSQL tests](https://github.com/seoyeonglee/audit-evidence-agent/actions/runs/36996099394) |

Browser testing also exposed concurrent first-request bootstrap and inherited mobile min-width. Bootstrap is now serialized once per process; the mobile layout regression checks document width. A failed additional document now marks canonical completeness false and appends a processing exception.

Remaining boundaries: demo bootstrap uses one API process; the UI uses public fictional sessions rather than production SSO; conflicting/dead sources need a future supervised supersession workflow; PDF normalization is a separate helper rather than a binary upload UI; no real model/OCR/cloud throughput benchmark has been run. These are disclosed capability boundaries, not hidden success claims.
