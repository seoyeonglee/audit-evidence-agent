# Graph recovery

1. Read the authenticated run detail and node events. `waiting_review` is an intentional durable interruption, not an execution timeout.
2. Submit the independent review with its original snapshot version and an idempotency key. Retry the same payload/key if its receipt was lost. Changing payload under that key returns 409.
3. Run a bounded demo graph tick (reviewer-only) or invoke `GraphRunner.tick()` in the single-host trusted runner. A committed command resumes the same thread without another canonical approval.
4. If evidence changed before review, reload the current request, finish extraction, and start a new run at the new version. The old input remains frozen; stale approval is denied.
5. A dead process leaves a lease. Once expired, the next runner claims it with a new token. Do not bypass the checkpoint file lock: it also prevents concurrent writers when execution exceeds its SQL lease.
6. `failed` after three attempts is terminal. Inspect safe error type, runtime configuration and checkpoint permissions. Preserve the old run, command and events. Do not delete audit history to repair a report.

The public free-host demo may lose local SQL/checkpoint files on redeploy. It is synthetic and ephemeral. Local desktop userData survives application restart on the same machine. Back up the domain database and checkpoint directory together before changing persistence profiles.
