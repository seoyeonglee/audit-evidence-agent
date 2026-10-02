# ADR-002: Authorization in the service and database

Status: accepted for this reference implementation.

## Context

Different tenants and participants share one service; a missing application filter must not expose another organization.

## Options

Application predicates alone; PostgreSQL tenant RLS plus service role scope; a database per organization.

## Decision

Resolve identity from opaque membership tokens, apply role/assignment scope in service methods and tenant RLS under a non-bypass runtime role.

## Trade-offs

RLS adds a defense against omitted tenant filters but does not replace vendor/request permissions. Session context must be transaction-local and migration credentials separate. SQLite does not implement RLS.
