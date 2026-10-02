# ADR-006: Append-only history with explicit trust limits

Status: accepted for this reference implementation.

## Context

Changing source facts and reviews must leave a trace a reviewer can inspect.

## Options

Mutable latest-review row; application-only event log; database-trigger-enforced events and per-request hash chains; external WORM log.

## Decision

Append events in the same transaction as domain changes, reject UPDATE/DELETE and verify a SHA-256 chain over deterministic event serialization.

## Trade-offs

Application users cannot rewrite events, and partial tampering breaks verification. A privileged database operator can alter the whole chain or disable triggers. External signed checkpoints/WORM remain future hardening.
