import pandas as pd

from src.scoring import assess_control, score_candidate


def control(**overrides):
    row = pd.Series({
        "control_id": "C1",
        "title": "Access review",
        "requirement": "Review access",
        "required_evidence_type": "access_review",
        "target_period": "Q3-2026",
        "keywords": "privileged|review|approved|revoked",
    })
    for key, value in overrides.items():
        row[key] = value
    return row


def test_supported_evidence_scores_high():
    evidence = pd.Series({
        "evidence_id": "E1",
        "evidence_type": "access_review",
        "period": "Q3-2026",
    })
    result = score_candidate(
        control(),
        evidence,
        "Privileged access review completed. Access approved and unnecessary access revoked.",
    )
    assert result["score"] == 100
    assert result["type_match"] is True
    assert result["period_match"] is True


def test_missing_required_evidence_type():
    index = pd.DataFrame([{
        "evidence_id": "E2",
        "filename": "other.txt",
        "evidence_type": "backup_test",
        "period": "Q3-2026",
        "owner": "Ops",
    }])
    result = assess_control(
        control(),
        index,
        {"E2": "backup restored successfully"},
    )
    assert result.status == "missing"
    assert result.score == 0


def test_exception_reduces_score():
    evidence = pd.Series({
        "evidence_id": "E1",
        "evidence_type": "access_review",
        "period": "Q3-2026",
    })
    good = score_candidate(
        control(), evidence,
        "Privileged review approved and revoked."
    )
    exception = score_candidate(
        control(), evidence,
        "Privileged review approved and revoked. pending remediation."
    )
    assert exception["score"] < good["score"]
