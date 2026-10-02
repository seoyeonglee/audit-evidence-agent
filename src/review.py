from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .trace import append_jsonl, utc_now
except ImportError:
    from trace import append_jsonl, utc_now


VALID_REVIEW_DECISIONS = {"approve", "reject", "needs_changes"}


def record_review(
    run_id: str,
    control_id: str,
    decision: str,
    reviewer: str,
    feedback: str = "",
    path: str = "output/reviewer_feedback.jsonl",
) -> dict:
    decision = decision.lower().strip()
    if decision not in VALID_REVIEW_DECISIONS:
        raise ValueError(
            f"decision must be one of {sorted(VALID_REVIEW_DECISIONS)}"
        )

    record = {
        "timestamp": utc_now(),
        "run_id": run_id,
        "control_id": control_id,
        "reviewer": reviewer,
        "decision": decision,
        "feedback": feedback,
    }
    append_jsonl(path, record)
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--control-id", required=True)
    parser.add_argument(
        "--decision",
        required=True,
        choices=sorted(VALID_REVIEW_DECISIONS),
    )
    parser.add_argument("--reviewer", default="portfolio-reviewer")
    parser.add_argument("--feedback", default="")
    parser.add_argument(
        "--path", default="output/reviewer_feedback.jsonl"
    )
    args = parser.parse_args()

    record = record_review(
        run_id=args.run_id,
        control_id=args.control_id,
        decision=args.decision,
        reviewer=args.reviewer,
        feedback=args.feedback,
        path=args.path,
    )
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
