from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


POSITIVE_STATUSES = {"gap", "missing"}


def evaluate_predictions(
    predictions: pd.DataFrame,
    expected: pd.DataFrame,
) -> dict:
    merged = expected.merge(
        predictions[
            [
                "control_id",
                "status",
                "grounded",
                "citation_valid",
            ]
        ],
        on="control_id",
        how="left",
        validate="one_to_one",
    )

    merged["predicted_positive"] = merged["status"].isin(
        POSITIVE_STATUSES
    )
    merged["expected_positive"] = merged["expected_status"].isin(
        POSITIVE_STATUSES
    )

    tp = int(
        (merged["predicted_positive"] & merged["expected_positive"]).sum()
    )
    fp = int(
        (merged["predicted_positive"] & ~merged["expected_positive"]).sum()
    )
    fn = int(
        (~merged["predicted_positive"] & merged["expected_positive"]).sum()
    )
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    false_positive_rate = (
        fp / int((~merged["expected_positive"]).sum())
        if int((~merged["expected_positive"]).sum())
        else 0.0
    )

    exact = float(
        (merged["status"] == merged["expected_status"]).mean()
    )
    grounded_rate = float(merged["grounded"].fillna(False).mean())
    citation_valid_rate = float(
        merged["citation_valid"].fillna(False).mean()
    )
    hallucination_proxy_rate = 1.0 - grounded_rate

    return {
        "examples": int(len(merged)),
        "exact_status_accuracy": round(exact, 4),
        "exception_precision": round(precision, 4),
        "exception_recall": round(recall, 4),
        "false_positive_rate": round(false_positive_rate, 4),
        "citation_valid_rate": round(citation_valid_rate, 4),
        "grounded_rate": round(grounded_rate, 4),
        "hallucination_proxy_rate": round(
            hallucination_proxy_rate, 4
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--predictions", default="output/agent_decisions.json"
    )
    parser.add_argument(
        "--expected", default="eval/expected_outputs.csv"
    )
    parser.add_argument("--output", default="output/evaluation.json")
    args = parser.parse_args()

    predictions = pd.read_json(args.predictions)
    expected = pd.read_csv(args.expected)
    metrics = evaluate_predictions(predictions, expected)

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
