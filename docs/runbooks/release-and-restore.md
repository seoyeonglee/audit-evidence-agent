# Release, rollback and restore

## Release

Run backend, real PostgreSQL integration, typecheck/build and browser workflow checks. Compare extraction evaluation if semantics changed. For a private deployment, back up first and migrate with a separate owner credential; runtime role must not own tables or bypass RLS. Start the worker only after migration and verify identity, tenant reads and an authorized test submission.

The existing Render services automatically deploy main. Set DEMO_MODE=1 explicitly only for the public synthetic service. No new paid resource is provisioned by this repository. The free demo filesystem is ephemeral, so a redeploy can reset SQLite data.

## Rollback

Keep the previous application image/commit and avoid destructive schema changes. Current bootstrap is additive create-if-missing, not a general migration framework. Before introducing a new incompatible canonical schema, add an explicit versioned migration and maintain reader compatibility during deployment. Do not roll back by deleting evidence, jobs or audit events.

## Restore verification

PostgreSQL: restore a managed backup into an isolated environment, apply the runtime grants/RLS policies, confirm counts and foreign keys, verify audit chains, ensure approved records remain immutable and test a fresh job/lease path. SQLite: take a consistent backup using SQLite's backup API or quiesce writers; copying only the main file while WAL writes continue is not a valid recovery procedure.

Recovery time and recovery point objectives are intentionally unset until the deployment and retention requirements are known. No backup/restore drill against a production database has been performed; this runbook is a release prerequisite, not evidence that it already happened.
