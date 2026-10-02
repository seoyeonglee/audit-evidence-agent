# ADR-005: Source facts before probabilistic judgment

Status: accepted for this reference implementation.

## Context

An audit conclusion must distinguish exact evidence facts, inferred interpretation and final human approval.

## Options

Let a model update records directly; use unvalidated parsing; validate structured facts and route judgment to an independent reviewer.

## Decision

The v2 pipeline uses exact structured source parsing, schema/calendar validation and explicit exceptions. Optional probabilistic RAG remains in the v1 lab; it cannot overwrite an approved v2 record.

## Trade-offs

The offline demo is reproducible and source-checkable, but general PDFs/OCR/free prose are not solved by this parser. Rule completeness is not calibrated model confidence and synthetic exact-match scores are not LLM accuracy.
