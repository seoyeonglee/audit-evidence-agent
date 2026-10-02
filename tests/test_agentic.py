from src.agentic import run_agentic_review


def test_agentic_review_is_grounded_and_reviewable():
    result, traces = run_agentic_review(provider="heuristic")
    assert len(result) == 6
    assert len(traces) == 6
    assert result["citation_valid"].all()
    assert result["grounded"].all()
    assert set(result["review_status"]) == {"pending"}

    statuses = dict(zip(result["control_id"], result["status"]))
    assert statuses["AC-01"] == "supported"
    assert statuses["LG-01"] == "missing"
