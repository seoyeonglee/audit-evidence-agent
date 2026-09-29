from pathlib import Path

import pandas as pd

from src.agent import run_assessment


def test_agent_assesses_synthetic_package():
    result = run_assessment(
        "data/controls.csv",
        "data/evidence_index.csv",
        "data/evidence",
    )
    assert len(result) == 6
    statuses = dict(zip(result["control_id"], result["status"]))
    assert statuses["AC-01"] == "supported"
    assert statuses["TP-01"] == "partial"
    assert statuses["LG-01"] == "missing"
