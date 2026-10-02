from src.review import record_review
from src.trace import read_jsonl


def test_reviewer_feedback_is_append_only(tmp_path):
    target = tmp_path / "feedback.jsonl"
    record_review(
        run_id="run-1",
        control_id="AC-01",
        decision="approve",
        reviewer="alice",
        feedback="Evidence is sufficient for pre-review.",
        path=str(target),
    )
    rows = read_jsonl(target)
    assert rows[0]["decision"] == "approve"
    assert rows[0]["control_id"] == "AC-01"
