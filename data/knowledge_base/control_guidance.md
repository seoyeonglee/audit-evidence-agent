# Synthetic Control Guidance

> This file contains synthetic, portfolio-only control guidance. It does not reproduce ISO, SOC 2, or any employer/customer control text.

## Access governance

A defensible privileged-access review should identify the population in scope, show that a reviewer evaluated retained access, document approval, and show how unnecessary access was removed. Evidence should be attributable to a review period and reviewer or control owner.

## Change management

Change evidence should connect a production change to authorization, testing, implementation, and the approved deployment context. Open follow-up items or failed validation should be surfaced to the human reviewer rather than hidden by an otherwise complete ticket.

## Backup and recovery

Recovery evidence should demonstrate that a backup was actually restored, validation occurred, and results were documented. A policy statement alone is not operating evidence.

## Third-party review

Vendor-security evidence should show that a relevant assessment occurred for the target period and that material open issues or pending approvals remain visible. Out-of-period evidence may be useful context but should not silently satisfy the current-period requirement.

## Termination access

Termination evidence should support timely removal of access and retain enough detail for a reviewer to identify delayed revocation. Any item outside the expected revocation window should be surfaced as an exception.

## Security logging

Logging evidence should demonstrate monitoring or review behavior, alerting where required, and defined retention. The absence of the required evidence type must remain a missing-evidence condition rather than being filled with a semantically similar but unrelated document.

## Human review and traceability

AI-assisted audit review should remain reviewable. Every material conclusion should link to the control requirement and evidence sources used. Low-confidence or exception-bearing results should be routed to a human reviewer. Reviewer approval, rejection, and feedback should be retained as separate events rather than overwriting the model output.
