from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

try:
    from .loaders import (
        load_controls,
        load_evidence_index,
        load_evidence_texts,
    )
    from .scoring import assess_control
except ImportError:
    from loaders import (
        load_controls,
        load_evidence_index,
        load_evidence_texts,
    )
    from scoring import assess_control


def run_assessment(
    controls_path: str,
    evidence_index_path: str,
    evidence_dir: str,
) -> pd.DataFrame:
    controls = load_controls(controls_path)
    evidence_index = load_evidence_index(evidence_index_path)
    evidence_texts = load_evidence_texts(
        evidence_index, evidence_dir
    )

    rows = []
    for _, control in controls.iterrows():
        assessment = assess_control(
            control, evidence_index, evidence_texts
        )
        row = asdict(assessment)
        row["control_title"] = str(control["title"])
        row["requirement"] = str(control["requirement"])
        rows.append(row)

    out = pd.DataFrame(rows)
    return out[
        [
            "control_id",
            "control_title",
            "requirement",
            "best_evidence_id",
            "evidence_type_match",
            "period_match",
            "keyword_coverage",
            "exception_terms",
            "score",
            "status",
            "reasoning",
        ]
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--controls", default="data/controls.csv"
    )
    parser.add_argument(
        "--evidence-index",
        default="data/evidence_index.csv",
    )
    parser.add_argument(
        "--evidence-dir", default="data/evidence"
    )
    parser.add_argument(
        "--output",
        default="output/control_assessment.csv",
    )
    parser.add_argument(
        "--summary", default="output/summary.json"
    )
    args = parser.parse_args()

    result = run_assessment(
        args.controls,
        args.evidence_index,
        args.evidence_dir,
    )

    serializable = result.copy()
    serializable["exception_terms"] = serializable[
        "exception_terms"
    ].apply(lambda x: "|".join(x))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    serializable.to_csv(output, index=False)

    counts = result["status"].value_counts().to_dict()
    summary = {
        "controls_assessed": int(len(result)),
        "supported": int(counts.get("supported", 0)),
        "partial": int(counts.get("partial", 0)),
        "gap": int(counts.get("gap", 0)),
        "missing": int(counts.get("missing", 0)),
        "average_score": round(float(result["score"].mean()), 2)
        if len(result)
        else 0.0,
        "note": (
            "This is a deterministic portfolio demonstration. "
            "Scores organize evidence for review; they do not replace auditor judgment."
        ),
    }
    Path(args.summary).write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
