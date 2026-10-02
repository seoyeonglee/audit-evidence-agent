# Scaling strategy based on the measured workload

The local benchmark processed 1,000 small structured documents over 100 records with a single offline worker. The record-read benchmark used 500 in-process ASGI requests and eight concurrent clients. Raw timings, backend and environment are in `reports/benchmark.json`. This does not model OCR, LLM calls, network/TLS, large binaries or 1,000 simultaneous users.

SQLite deliberately serializes transactions. The measured p95/p99 tail is considerably larger than p50 under concurrency, so do not infer private-production capacity from its throughput. Move the deployment profile to PostgreSQL before tuning distributed concurrency. The direct PostgreSQL tests establish queue/security correctness, not a PostgreSQL throughput benchmark.

1. Establish actual queue age, extraction duration and database wait/connection metrics.
2. Separate API and worker pools; cap aggregate connections below the database budget with headroom for migrations/administration.
3. Increase tenant workers gradually; use SKIP LOCKED and confirm claim uniqueness, fairness and tail latency.
4. Move large binaries to tenant-scoped object storage; retain source digests and authorized retrieval.
5. Add worker lease renewal for long external OCR/model calls; current 30-second lease is appropriate only to the small offline parser workload.
6. If queue polling/history creates measured database pressure, introduce an outbox and SQS/Redis adapter; keep idempotency and lease/result fencing semantics.

A rough planning relationship is worker concurrency ≥ arrival rate × observed mean processing time, with explicit headroom and model-rate limits. Validate it with representative documents and record distributions. Split services only when a component needs independent ownership, scaling or failure isolation that the current modular boundary cannot provide.
