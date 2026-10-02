# ADR-003: Modular monolith with an independent worker

Status: accepted for this reference implementation.

## Context

The proof needs reliable workflow behavior and comprehensible operations; no evidence yet justifies a service mesh.

## Options

A single blocking HTTP app; separately deployed microservices; a modular API with independent document worker.

## Decision

Keep auth, domain and persistence in one application boundary. Run document processing independently behind the leased queue.

## Trade-offs

Interfaces remain explicit and deployment count is low. Separate scaling or failure isolation may eventually justify moving extraction to a service; current benchmarks do not establish that need.
