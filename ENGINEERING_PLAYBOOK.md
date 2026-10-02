# Engineering ownership playbook

This is an operating proposal for this reference system, not a claim that a real engineering team already follows it.

## Change and review

Use a focused feature branch and PR tied to a concrete workflow or failure mode. The PR explains the trigger and resulting behavior, identifies domain and authorization changes, links test evidence, and states migration/rollback implications. Approval from a reviewer who did not author the change is required for private-production release. The portfolio change received an independent code review; its findings and fixes are documented in `docs/review-findings.md`.

Authorization changes require both denied and allowed paths. Queue changes require duplicate, expired-lease and terminal-failure behavior. Extraction changes require independently labeled expected facts and exact source lineage, including unknown/malformed input. These tests protect observable behavior; line coverage is a diagnostic, not a release argument.

## Release gates

1. Backend behavior and security suite passes.
2. PostgreSQL migration/RLS/concurrency integration passes under a non-bypass role.
3. TypeScript typecheck and production bundle build pass.
4. Browser submission→processing→approval and role scope pass.
5. If extraction semantics changed, run the offline corpus and inspect changed outcomes.
6. Review the deploy profile: demo opt-in, database credentials, worker tenant, rollback version and backup.

CI retains JUnit results, coverage XML, browser results/screenshots and failed traces as artifacts. Measured benchmark/evaluation files have explicit environment and provider labels. A green pipeline is evidence of those contracts, not certification of general AI accuracy.

## Ownership and incidents

API owns membership/scope and request transitions; worker owns queue claim/recovery; extractor owns source fidelity; reviewer owns final conclusion. In a small team the same engineer may operate multiple components, but logs and interfaces preserve these boundaries.

SEV1: unauthorized data access or approved-record corruption. Stop relevant writes, preserve evidence, revoke affected credentials and involve the security owner. SEV2: processing unavailable or sustained queue growth. Cap concurrency, inspect lease/backoff/DLQ and recover per runbook. SEV3: degraded latency or presentation issue. Capture workload and reproduce before changing architecture.

Never mutate old audit events to repair an incident. Record corrective actions separately. If a schema change is not backward-compatible, deploy a compatible read/write bridge before replacing the old worker. Rolling back application code must not require deleting submitted documents or reviewer events.
