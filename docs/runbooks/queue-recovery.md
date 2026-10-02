# Queue recovery

1. Determine affected tenant and requests. Inspect `/api/v2/metrics` and each record's jobs/events using an authorized membership token; don't print source documents or tokens into shared logs.
2. Confirm the worker is running with the intended DATABASE_URL and `--tenant`. API and worker must point to the same durable database.
3. For queued jobs, restart the worker normally. Claims are leased; do not manually mark jobs succeeded.
4. For expired running jobs, a subsequent claim issues a new lease token and increments attempts. An old worker's callback is rejected. After the attempt budget, recovery sends the job to dead_letter.
5. For retryable failures, inspect sanitized error type and available_at. Backoff is exponential. Do not run many parallel workers to force retries earlier.
6. For dead letters, preserve source digest, job ID and event history. The current reference has no administrative replay/supersession endpoint. Human handling or a new separately reviewed request is required; do not directly edit canonical facts or audit history.
7. Recheck completeness and exception codes before review. Record any incident remediation separately and verify the event chain.

Worker shutdown handles SIGTERM/SIGINT by finishing the current bounded tick and exiting. A forced termination is handled through lease expiration, not an assumed successful job. External processing that can exceed the lease requires a future heartbeat/renewal mechanism.
