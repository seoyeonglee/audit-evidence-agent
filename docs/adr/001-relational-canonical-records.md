# ADR-001: Relational canonical records

Status: accepted for this reference implementation.

## Context

One request must reconcile several source documents, asynchronous attempts and independently authorized reviewers.

## Options

PostgreSQL relationships with JSON canonical facts; a document database; append-only event sourcing for every state.

## Decision

Use relational integrity for tenant/request/document/job associations and JSON only for evolving extracted fields. Store the current record beside its append-only decision history.

## Trade-offs

Foreign keys and transactions protect workflow invariants. JSON facts need explicit schema validation; this is not a full event-sourced reconstruction engine.
