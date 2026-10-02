"""Versioned offline evaluation. This is not an LLM benchmark."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from src.platform.extraction import PermanentError, canonical_record, extract


def evaluate_corpus(corpus):
    matched = total = unsupported = predicted = 0
    quarantine_tp = quarantine_fn = quarantine_fp = 0
    exception_tp = exception_fn = exception_fp = 0
    outcomes = []
    for case in corpus:
        actual = {}
        codes = []
        quarantined = False
        try:
            extraction = extract(
                {
                    "id": case["id"],
                    "content": case["content"],
                    "media_type": case["media_type"],
                    "digest": hashlib.sha256(case["content"].encode()).hexdigest(),
                }
            )
            actual = {k: f["value"] for k, f in extraction["fields"].items()}
            canonical = canonical_record([extraction], "2026-Q3")
            codes = sorted({e["code"] for e in canonical["exceptions"]})
        except PermanentError:
            quarantined = True
        expected = case["expected"]
        matched += sum(actual.get(k) == v for k, v in expected.items())
        total += len(expected)
        unsupported += len(set(actual) - set(expected))
        predicted += len(actual)
        quarantine_tp += quarantined and case["quarantine"]
        quarantine_fn += not quarantined and case["quarantine"]
        quarantine_fp += quarantined and not case["quarantine"]
        expected_codes = set(case["expected_codes"])
        observed = set(codes)
        exception_tp += len(expected_codes & observed)
        exception_fn += len(expected_codes - observed)
        exception_fp += len(observed - expected_codes)
        outcomes.append(
            {
                "id": case["id"],
                "actual": actual,
                "exception_codes": codes,
                "quarantined": quarantined,
                "passed": actual == expected
                and observed == expected_codes
                and quarantined == case["quarantine"],
            }
        )
    ratio = lambda a, b: a / b if b else 1.0
    return {
        "provider": "deterministic-key-value-v1",
        "scope": "synthetic structured text/CSV/JSON; no OCR or external LLM calls",
        "cases": len(corpus),
        "expected_fields": total,
        "case_accuracy": sum(r["passed"] for r in outcomes) / len(corpus),
        "field_exact_match": ratio(matched, total),
        "unsupported_field_rate": unsupported / max(1, predicted),
        "quarantine_precision": ratio(quarantine_tp, quarantine_tp + quarantine_fp),
        "quarantine_recall": ratio(quarantine_tp, quarantine_tp + quarantine_fn),
        "exception_precision": ratio(exception_tp, exception_tp + exception_fp),
        "exception_recall": ratio(exception_tp, exception_tp + exception_fn),
        "outcomes": outcomes,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", default="eval/platform-corpus.json")
    parser.add_argument("--output", default="docs/reports/evaluation.json")
    args = parser.parse_args()
    source = Path(args.corpus)
    corpus = json.loads(source.read_text())
    report = evaluate_corpus(corpus)
    report.update(
        {
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "corpus_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "limitations": [
                "Rule parser evaluated on generated structured examples; general document/LLM quality is not established.",
                "Labels are authored scenarios, not independent human annotations of real audits.",
                "Source attribution checks do not detect every semantic hallucination or prompt injection.",
            ],
        }
    )
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "outcomes"}, indent=2))


if __name__ == "__main__":
    main()
