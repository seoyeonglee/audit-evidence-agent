"""Actual compiled graph over independently labeled synthetic cases; no LLM claims."""

import json
import tempfile
from pathlib import Path
from src.platform.extraction import extract, canonical_record, PermanentError
from src.platform.service import digest
from src.enterprise.graph import build_graph
from src.enterprise.checkpoints import CheckpointManager


def main():
    outcomes = []
    corpus = json.loads(Path("eval/enterprise-corpus.json").read_text())
    with tempfile.TemporaryDirectory() as directory:
        cp = CheckpointManager(directory)
        for case in corpus:
            docs, extracted = [], []
            for index, content in enumerate(case["documents"]):
                doc = {
                    "id": f"{case['id']}-{index}",
                    "filename": "synthetic.txt",
                    "media_type": "text/plain",
                    "content": content,
                    "digest": digest(content),
                }
                try:
                    doc["extraction"] = extract(doc)
                    extracted.append(doc["extraction"])
                except PermanentError:
                    doc["extraction"] = None
                docs.append(doc)
            snapshot = {
                "request_id": case["id"],
                "title": "Access review",
                "version": 2,
                "control_id": "AC-01",
                "period": "2026-Q3",
                "documents": docs,
                "canonical": canonical_record(extracted, "2026-Q3"),
            }
            if case.get("tamper_digest"):
                docs[0]["digest"] = "0" * 64
            with cp.open("evaluation") as saver:
                result = build_graph(saver).invoke(
                    {"run_id": case["id"], "snapshot": snapshot},
                    {"configurable": {"thread_id": case["id"]}},
                )
            actual = result["assessment"]["recommendation"]
            outcomes.append(
                {
                    "id": case["id"],
                    "expected": case["expected"],
                    "actual": actual,
                    "grounding": result["grounding"],
                    "passed": actual == case["expected"],
                }
            )
    report = {
        "provider": "offline-heuristic-v1",
        "scope": "7 labeled synthetic graph cases; source validation and advisory routing, not LLM accuracy",
        "passed": sum(r["passed"] for r in outcomes),
        "total": len(outcomes),
        "outcomes": outcomes,
    }
    Path("docs/reports/enterprise-evaluation.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(f"Enterprise graph cases: {report['passed']}/{report['total']}")
    if not all(r["passed"] for r in outcomes):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
