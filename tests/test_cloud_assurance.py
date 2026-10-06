from copy import deepcopy
from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)


def sample():
    r = client.get("/api/cloud-assurance/sample")
    assert r.status_code == 200
    return r.json()


def assess(bundle):
    r = client.post("/api/cloud-assurance/assess", json=bundle)
    assert r.status_code == 200, r.text
    return {row["id"]: row for row in r.json()["results"]}


def test_sample_distinguishes_gap_missing_stale_and_ready():
    rows = assess(sample())
    assert rows["CC-IAM"]["status"] == "ready_for_review"
    assert rows["CC-STORAGE"]["status"] == "gap"
    assert rows["CC-LOG"]["status"] == "stale"
    assert rows["CC-KEY"]["status"] == "missing"
    assert rows["CC-VENDOR"]["status"] == "manual_review"


def test_missing_empty_and_string_booleans_never_pass():
    bundle = sample()
    bundle["evidence"]["iam"]["data"] = {}
    assert assess(bundle)["CC-IAM"]["status"] == "missing"
    bundle["evidence"]["iam"]["data"] = {"AccountMFAEnabled": "true"}
    assert assess(bundle)["CC-IAM"]["status"] == "missing"


def test_future_and_out_of_scope_evidence_are_not_accepted():
    bundle = sample()
    bundle["evidence"]["iam"]["collected_at"] = "2030-01-01"
    assert assess(bundle)["CC-IAM"]["status"] == "invalid"
    bundle = sample()
    bundle["evidence"]["iam"]["account_id"] = "other-account"
    assert assess(bundle)["CC-IAM"]["status"] == "out_of_scope"


def test_bucket_check_is_strict_baseline_not_public_exposure_claim():
    bundle = sample()
    data = bundle["evidence"]["s3"]["data"]["PublicAccessBlockConfiguration"]
    for key in data:
        data[key] = True
    row = assess(bundle)["CC-STORAGE"]
    assert row["status"] == "ready_for_review"
    assert "bucket" in row["scope_limit"].lower()
    del data["BlockPublicPolicy"]
    assert assess(bundle)["CC-STORAGE"]["status"] == "missing"


def test_hash_is_reproducible_and_changes_with_evidence():
    bundle = sample()
    first = assess(bundle)["CC-IAM"]["evidence_sha256"]
    assert first == assess(deepcopy(bundle))["CC-IAM"]["evidence_sha256"]
    bundle["evidence"]["iam"]["data"]["AccountMFAEnabled"] = 0
    assert first != assess(bundle)["CC-IAM"]["evidence_sha256"]


def test_invalid_date_and_oversized_input_rejected():
    bundle = sample()
    bundle["as_of"] = "2026-02-30"
    assert client.post("/api/cloud-assurance/assess", json=bundle).status_code == 422
    bundle = sample()
    bundle["evidence"]["iam"]["data"]["padding"] = "x" * 100001
    assert client.post("/api/cloud-assurance/assess", json=bundle).status_code == 422


def test_framework_links_are_candidates_with_separate_korean_schemes():
    response = client.get("/api/cloud-assurance/catalog")
    assert response.status_code == 200
    catalog = response.json()
    assert len(catalog["controls"]) == 8
    assert {"CSAP", "CSP Safety"} <= set(catalog["frameworks"])
    assert all(
        m["relationship"] == "candidate_domain_overlap"
        for c in catalog["controls"]
        for m in c["mappings"]
    )


def test_global_scope_only_applies_to_account_wide_iam():
    bundle = sample()
    bundle["evidence"]["s3"]["region"] = "global"
    assert assess(bundle)["CC-STORAGE"]["status"] == "out_of_scope"
    bundle["evidence"]["iam"]["region"] = "global"
    assert assess(bundle)["CC-IAM"]["status"] == "ready_for_review"


def test_nonfinite_numbers_rejected_before_response_serialization():
    import json

    bundle = sample()
    bundle["evidence"]["iam"]["data"]["AccountMFAEnabled"] = float("inf")
    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/cloud-assurance/assess",
        content=json.dumps(bundle),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
