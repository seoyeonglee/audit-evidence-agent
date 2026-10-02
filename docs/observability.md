# Observability and measurable signals

`GET /api/v2/metrics` derives request, job-state, retry and approval counts from persisted tenant-scoped data. Owner/vendor metrics include only assigned requests. It does not display fabricated API latency, synthetic historical traffic or sampled live model success rates.

`GET /api/v2/measurements` exposes checked-in reports from measured local runs. These are labeled historical synthetic measurements, not current production metrics. Queue states in the Operations panel are current; evaluation/benchmark cards are checked-in runs.

Worker structured logs include event type, job ID, tenant ID and attempt count. Persisted events join request, document and job IDs to review decisions. Retry/dead-letter records store exception type only, avoiding copied document contents, secrets or raw model prompts in errors. `request_id` plus `job_id` provides correlation; this is not a deployed OpenTelemetry trace backend.

| Signal | Interpretation | Initial operator action |
|---|---|---|
| queued growing / no running jobs | Worker stopped or claims failing | Verify tenant configuration, credentials and worker process |
| running leases repeatedly expire | Worker crash or processing exceeds lease | Inspect errors and workload; keep concurrency bounded |
| retry attempts rising | Transient extraction/dependency failure | Inspect sanitized error type; respect backoff |
| dead letters rising | Invalid/unsupported source or exhausted retries | Human handling; preserve source/event history |
| read p95/p99 much higher than p50 | Lock contention or variable record size | Reproduce same backend/concurrency and measure transaction wait |
| grounding/citation validity regression | Retrieval/provider contract drift in RAG Lab | Inspect source IDs and changed corpus/provider before release |

Alert thresholds require real traffic baselines. Do not assert an SLO based only on a small local demo. No production paging or alert vendor has been configured.
