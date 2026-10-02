# ADR-004: A transactional SQL queue first

Status: accepted for this reference implementation.

## Context

Storing evidence and publishing to an external queue creates a two-write failure mode.

## Options

PostgreSQL jobs; Redis/BullMQ with an outbox; SQS with an outbox; blocking synchronous processing.

## Decision

Insert document, job and event in one transaction. Claim with leases and SKIP LOCKED; enforce attempt budget and token fencing.

## Trade-offs

One database is operationally simpler and gives atomic intake. Claim polling and queue retention add DB load. Introduce an external queue only after measured contention, preserving an outbox and idempotent consumers.
