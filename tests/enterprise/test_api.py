from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.enterprise.routes import create_router
from src.enterprise.checkpoints import CheckpointManager


def test_actual_api_executes_review_and_exports(enterprise_fixture):
    store, svc, users, tokens, _, root = enterprise_fixture
    app = FastAPI()
    app.include_router(
        create_router(store, CheckpointManager(root / "api-cp"), True, tokens)
    )
    client = TestClient(app)
    h = {
        "Authorization": "Bearer " + tokens["reviewer"],
        "Idempotency-Key": "api-start",
    }
    assert client.get("/api/v2/agent-runs/missing").status_code == 401
    start = client.post(
        "/api/v2/requests/REQ-ACCESS/agent-runs", headers=h, json={"version": 2}
    )
    assert start.status_code == 202
    rid = start.json()["id"]
    assert (
        client.post("/api/v2/demo/agent-process", headers=h, json={}).status_code == 200
    )
    detail = client.get("/api/v2/agent-runs/" + rid, headers=h).json()
    assert detail["status"] == "waiting_review"
    assert [e["node"] for e in detail["events"]][:5] == [
        "load_snapshot",
        "guardrails",
        "retrieve",
        "assess",
        "validate_grounding",
    ]
    assert (
        client.post(
            f"/api/v2/agent-runs/{rid}/review",
            headers={**h, "Idempotency-Key": "api-review"},
            json={"version": 2, "decision": "approve", "feedback": "Verified"},
        ).status_code
        == 200
    )
    client.post("/api/v2/demo/agent-process", headers=h, json={})
    report = client.get(f"/api/v2/agent-runs/{rid}/report?format=markdown", headers=h)
    assert (
        report.status_code == 200 and "Sources" not in report.text
    )  # actual excerpts follow
    assert "production-admin" in report.text
    assert (
        client.get(
            "/api/v2/agent-runs/" + rid,
            headers={"Authorization": "Bearer " + tokens["other-reviewer"]},
        ).status_code
        == 404
    )


def test_demo_endpoints_are_absent_without_optin(enterprise_fixture):
    app = FastAPI()
    app.include_router(create_router(enterprise_fixture[0], demo_enabled=False))
    assert (
        TestClient(app)
        .post("/api/v2/demo/agent-scenario", json={"scenario": "complete"})
        .status_code
        == 404
    )
