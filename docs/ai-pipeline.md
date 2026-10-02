# Extraction, RAG and evaluation

There are two deliberate pipelines, rather than one demo misleadingly labeled as production AI.

| Pipeline | Implemented provider | Output and limitations |
|---|---|---|
| Operations / v2 | Deterministic text, CSV and JSON parser | Typed facts with exact source spans; rejects malformed/unsupported facts; no external model call |
| RAG Lab / v1 | TF-IDF retrieval, heuristic guardrail reasoner; optional OpenAI reasoner | Control/evidence/guidance context, structured assessment and validated source IDs; independent synthetic sandbox |

Operations flow: submit normalized text → durable job → extract recognized facts → validate scalar types/calendar → reconcile sources → deterministic exception codes → independent reviewer. Duplicate fields are quarantined rather than silently taking the final value. Conflicting values across documents retain the sources and block approval. Source excerpts are facts' exact spans; they do not imply semantic verification of an entire document.

The worker stores the parser version/provider beside each extraction. For an LLM adapter, preserve this interface but validate output schema and require every fact to have a source span the server can verify. Treat uploaded text as untrusted data, never as authorization or instructions. Low-quality/unsupported extraction should fail conservatively and route to human handling. A model-generated confidence score must be evaluated/calibrated before it becomes a threshold.

The checked-in `eval/platform-corpus.json` has 100 authored synthetic cases: 60 valid examples over three input formats, 10 stale periods, 10 explicit exceptions, 10 missing-field cases and 10 adverse inputs. It contains 340 expected fields. `scripts.evaluate_platform` compares expected values and exception codes, measures unsupported-field and quarantine outcomes, and stores every case result plus corpus digest. The 100% result means these structured authored cases passed; it does not establish free-form extraction, OCR quality, real audit suitability or LLM hallucination rates.

The existing v1 evaluation separately measures exact status, exception precision/recall, citation validity and a limited hallucination proxy. Do not combine its metrics with v2 parser metrics or claim they measure semantic model correctness. Next useful evidence: independently labeled realistic documents, adversarial prompt corpus, a true OCR provider and an actual model evaluation with recorded model/version/latency/cost.
