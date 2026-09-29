# Methodology

## Purpose

This project demonstrates how audit evidence can be organized and pre-assessed before human review.

It is deliberately **not** an autonomous audit-opinion engine. The output helps prioritize evidence review; auditor judgment remains necessary.

## Assessment dimensions

### Evidence type
A control is only assessed against evidence items of the required type. If no item of that type exists, the status is `missing`.

### Period
Evidence receives credit when its documented period matches the control's target period.

### Keyword coverage
Control-specific keywords provide a transparent proxy for whether the evidence discusses expected review concepts.

### Exception terms
Explicit phrases such as `failed`, `overdue`, `missing`, and `pending remediation` reduce the score and remain visible in the reasoning trail.

## Status bands

- **supported**: score >= 80
- **partial**: score 50–79
- **gap**: score below 50
- **missing**: required evidence type not provided

## Why deterministic first?

A deterministic baseline makes it easy to:
- reproduce results
- test logic
- inspect why evidence was selected
- identify where an LLM would add value

A future LLM layer could summarize evidence, extract dates/owners, or draft workpaper language, while retaining this deterministic layer for validation and guardrails.

## Limitations

Real audits require much more than document keyword coverage. Production use would need:
- evidence authenticity and provenance
- population completeness
- sampling methodology
- control design and operating-effectiveness testing
- auditor independence
- contradiction resolution
- secure document handling
- retention and access controls
- human review and sign-off
