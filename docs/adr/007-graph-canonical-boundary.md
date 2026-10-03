# ADR 007 — Durable graph, authoritative canonical record

Accepted for the synthetic enterprise demo.

LangGraph owns advisory assessment and durable interruption. The canonical SQL service owns membership, scope, version checks, evidence facts and approval. A review transaction records the canonical event and immutable command together. The runner resumes from that command and never writes a second approval.

The frozen snapshot includes the selected request, parsed facts, raw source text, SHA256 digests and synthetic control/guidance definitions. Request-scoped TF-IDF retrieves at most six evidence spans; no global evidence corpus crosses request scope. Source validation routes invalid grounding to a blocked assessment. Human review is required even for complete evidence.

Per-tenant official SQLite checkpoints and a file lock deliberately constrain execution to one host. Leases fence relational writes; retries stop after three attempts. A checkpoint may precede its relational summary after a crash, so recovery reads the durable graph state. Approval may precede final report generation; recovery reads its immutable command.

Tradeoff: PostgreSQL secures domain tables, but the checkpoint files still require private filesystem permissions and one-host operation. Distributed checkpoint storage and hosted-model graph reasoning are future extensions. The existing optional provider remains in RAG Lab; this graph profile allows heuristic reasoning only.
