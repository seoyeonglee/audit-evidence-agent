# Release, rollback and restore

## Release

Run backend, real PostgreSQL integration, typecheck/build and browser workflow checks. Compare extraction evaluation if semantics changed. For a private deployment, back up first and migrate with a separate owner credential; runtime role must not own tables or bypass RLS. Start the worker only after migration and verify identity, tenant reads and an authorized test submission.

The existing Render services automatically deploy main. Set DEMO_MODE=1 explicitly only for the public synthetic service. No new paid resource is provisioned by this repository. The free demo filesystem is ephemeral, so a redeploy can reset SQLite data.

## Collaboration schema upgrade

The additive migration creates `invitations`, `external_sessions`, `document_revisions` and `invitation_accept_limits`. It first adds the unique `(tenant_id, request_id, id)` document index required by revision foreign keys. Existing documents, approvals and audit events are retained. Run it twice in staging and verify that the second run is a no-op.

After migrating with the owner credential, grant the runtime role access explicitly (replace `app_runtime` with the actual role):

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON invitations, external_sessions,
  document_revisions, invitation_accept_limits TO app_runtime;
```

The first three tables use tenant RLS. The acceptance limiter intentionally stores only peer hashes and counters globally; it must be accessible without tenant context. Runtime credentials must not own tables or have `BYPASSRLS`. Run the PostgreSQL runtime-role integration suite before deploying API and worker together.

## Rollback

Keep the previous application image/commit and avoid destructive schema changes. Current bootstrap is additive create-if-missing, not a general migration framework. Before introducing a new incompatible canonical schema, add an explicit versioned migration and maintain reader compatibility during deployment. Do not roll back by deleting evidence, jobs or audit events. For this collaboration release, disable invitation issuance/acceptance and quiesce writers before switching application versions. Preserve all four additive tables and the document index. Revoke live invitations before disabling endpoints. A pre-revision worker does not understand supersession and must not process requests containing revisions; keep the compatible worker or pause processing until the forward fix is deployed. Verify audit chains and request visibility before resuming writes.

## Restore verification

PostgreSQL: restore a managed backup into an isolated environment, apply the runtime grants/RLS policies, confirm counts and foreign keys, verify audit chains, ensure approved records remain immutable and test a fresh job/lease path. SQLite: take a consistent backup using SQLite's backup API or quiesce writers; copying only the main file while WAL writes continue is not a valid recovery procedure.

Recovery time and recovery point objectives are intentionally unset until the deployment and retention requirements are known. No backup/restore drill against a production database has been performed; this runbook is a release prerequisite, not evidence that it already happened.
