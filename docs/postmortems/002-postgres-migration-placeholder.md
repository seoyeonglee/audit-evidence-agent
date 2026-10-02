# PostgreSQL migration placeholder failure

Type: observed GitHub Actions integration failure. Date: 2026-10-02.

The first real PostgreSQL security job failed during migration, before nine RLS tests could run. psycopg reported `only '%s', '%b', '%t' are allowed as placeholders, got '%I'`. PL/pgSQL `format('%I', ...)` was passed through SQLAlchemy `exec_driver_sql` with driver parameter semantics.

Execute the migration through SQLAlchemy `text()` so the dialect escapes literal percent characters appropriately. Preserve the full PostgreSQL service job as the regression boundary; SQLite cannot exercise this driver interaction. The first run is linked in `../review-findings.md` and follow-up successful CI evidence belongs in `../reports/verification.json`.

Lesson: an unexecuted SQL reference is not a tested database profile. Keep migration and direct security assertions in the same actual PostgreSQL integration job, and retain logs/results on failure as well as success.

Verification: [initial failed CI](https://github.com/seoyeonglee/audit-evidence-agent/actions/runs/36991034568), [corrected CI: all three jobs passed](https://github.com/seoyeonglee/audit-evidence-agent/actions/runs/36996099394).
