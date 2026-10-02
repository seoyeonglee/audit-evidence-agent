import pandas as pd

from src.evaluate import evaluate_predictions


def test_evaluation_metrics_include_grounding():
    predictions = pd.DataFrame(
        [
            {
                "control_id": "A",
                "status": "gap",
                "grounded": True,
                "citation_valid": True,
            },
            {
                "control_id": "B",
                "status": "supported",
                "grounded": False,
                "citation_valid": False,
            },
        ]
    )
    expected = pd.DataFrame(
        [
            {"control_id": "A", "expected_status": "gap"},
            {"control_id": "B", "expected_status": "supported"},
        ]
    )

    metrics = evaluate_predictions(predictions, expected)
    assert metrics["exact_status_accuracy"] == 1.0
    assert metrics["exception_precision"] == 1.0
    assert metrics["grounded_rate"] == 0.5
    assert metrics["hallucination_proxy_rate"] == 0.5
