# Methodology

## Purpose

This project demonstrates an AI-assisted audit evidence workflow. It does not
issue audit opinions or autonomously determine control effectiveness. Its job
is to organize evidence, surface gaps and exceptions, ground AI conclusions in
retrieved sources, and route the result to a human reviewer.

## Pipeline

1. **Evidence intake** — load the control catalog, evidence metadata, and
   synthetic evidence documents.
2. **Control interpretation** — use the stated requirement, expected evidence
   type, target period, and synthetic guidance as review context.
3. **Deterministic validation** — check evidence type, period, keyword
   coverage, and explicit exception terms.
4. **RAG retrieval** — retrieve relevant control, evidence, and guidance
   chunks for the current control.
5. **Agent reasoning** — produce a structured decision containing status,
   confidence, evidence IDs, citations, missing evidence, exception language,
   and concise reasoning.
6. **Grounding validation** — reject citations that were not retrieved and
   flag evidence IDs that do not exist in the evidence index.
7. **Human review** — keep decisions pending until a reviewer records approve,
   reject, or needs-changes feedback.
8. **Trace storage** — retain the sources, baseline, AI output, and validation
   checks as append-only events.
9. **Evaluation** — compare results against a synthetic expected-output set.

## Status semantics

- **supported** — available evidence supports the pre-review requirement and
  no material exception was detected by the current checks.
- **partial** — evidence is relevant but incomplete, out of period, or contains
  an exception that requires human attention.
- **gap** — evidence exists but does not sufficiently support the requirement.
- **missing** — the required evidence type was not provided.

These are pre-review labels, not audit conclusions.

## RAG and citations

The repository deliberately uses synthetic control guidance rather than
copying proprietary standards or employer workpapers. Retrieved chunks receive
stable source IDs such as:

- `control:AC-01`
- `evidence:E001`
- `kb:control_guidance:access-governance`

The agent may cite only source IDs returned by retrieval. Post-generation
validation checks that every citation was actually in context.

## Hallucination controls

The implementation uses several controls rather than relying on prompting
alone:

- retrieved-context-only instructions
- allow-listed citations
- validation of evidence IDs against the source index
- deterministic baseline retained beside the AI result
- explicit missing-evidence output
- human sign-off required
- append-only model and reviewer traces

The evaluation harness reports a **hallucination proxy rate** based on whether
predictions remain grounded in valid citations/evidence IDs. It is a
portfolio metric, not a claim that all semantic hallucinations are detected.

## Evaluation metrics

The synthetic evaluation set tracks:

- exact status accuracy
- exception precision
- exception recall
- false-positive rate
- citation-valid rate
- grounded-result rate
- hallucination proxy rate

The dataset is intentionally small and transparent. Production evaluation
would require a larger expert-labeled corpus, per-control error analysis,
calibration, adversarial evidence, and regression suites.

## Human-in-the-loop

Reviewer actions are stored separately from the model result:

- `approve`
- `reject`
- `needs_changes`

Reviewer feedback can later be used for error analysis or supervised
evaluation. This project does not automatically fine-tune on reviewer input.

## Limitations

Production audit systems additionally require:
- evidence authenticity and provenance
- population completeness and sampling methodology
- control design and operating-effectiveness testing
- auditor independence
- secure document handling and tenant isolation
- retention and access controls
- model and prompt versioning
- privacy impact assessment
- secrets management
- authorization and role-based review workflows
- robust document parsing and OCR controls
- expert-labeled evaluation at meaningful scale
