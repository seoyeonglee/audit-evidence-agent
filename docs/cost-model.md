# Cost model

The public synthetic profile uses the existing static frontend and free Python service, local SQLite and offline parsing. It requires no paid model/OCR/object-store account. Hosting terms and quotas can change; this document makes no long-term free-tier guarantee.

For a private deployment, plan the monthly cost as:

`API compute + worker compute + managed PostgreSQL + backup/storage + object storage + outbound transfer + monitoring + OCR pages × unit price + model input/output tokens × unit price`.

Measure source size, pages, tokens, retries and retention before choosing a cloud SKU. Deduplicate identical inbound events before paid parsing; cache extraction by content digest only with tenant-safe lookup; require schema/source validation to avoid paying repeatedly for unusable output. Retain immutable originals only for the agreed period, and budget backup copies separately.

No pricing estimate or cloud bill is presented as measured. The local docs/minute benchmark has no model/OCR component and cannot predict model throughput or operating cost. The reference can support choosing SQL queue versus external queue, but an actual cost comparison needs the organization's traffic and current provider prices.
