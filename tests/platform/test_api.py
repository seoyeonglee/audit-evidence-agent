from test_workflow import system as system  # pytest fixture re-export
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_workflow import doc


@pytest.fixture
def client(system):
    from src.platform.routes import create_router
    from src.platform.auth import token_hash
    from src.platform.models import members
    from sqlalchemy import update

    store, _, _ = system
    tokens = {
        "owner": "owner-token",
        "reviewer": "reviewer-token",
        "vendor": "vendor-token",
        "other-reviewer": "other-token",
    }
    with store.transaction() as conn:
        for name, token in tokens.items():
            conn.execute(
                update(members)
                .where(members.c.id == name)
                .values(token_hash=token_hash(token))
            )
    app = FastAPI()
    app.include_router(create_router(store, tokens))
    return TestClient(app)


def test_token_required_and_tenant_header_is_not_authority(client):
    assert client.get("/api/v2/requests").status_code == 401
    response = client.get(
        "/api/v2/requests",
        headers={"Authorization": "Bearer vendor-token", "X-Tenant-ID": "demo-north"},
    )
    assert [r["id"] for r in response.json()["requests"]] == ["REQ-VENDOR"]
    assert (
        client.get(
            "/api/v2/requests/REQ-ACCESS",
            headers={"Authorization": "Bearer other-token"},
        ).status_code
        == 404
    )


def test_complete_http_workflow(client):
    owner = {"Authorization": "Bearer owner-token", "Idempotency-Key": "demo-submit"}
    response = client.post(
        "/api/v2/requests/REQ-ACCESS/documents", headers=owner, json=doc()
    )
    assert response.status_code == 202
    assert (
        client.post(
            "/api/v2/demo/process", headers={"Authorization": "Bearer owner-token"}
        ).status_code
        == 403
    )
    rev = {"Authorization": "Bearer reviewer-token"}
    assert client.post("/api/v2/demo/process", headers=rev).json()["processed"] == 1
    r = client.get("/api/v2/requests/REQ-ACCESS", headers=rev).json()
    assert r["canonical"]["complete"] is True
    assert (
        client.post(
            "/api/v2/requests/REQ-ACCESS/review",
            headers=rev,
            json={
                "version": r["version"],
                "decision": "approve",
                "feedback": "Source verified",
            },
        ).status_code
        == 200
    )
    history = client.get(
        "/api/v2/requests/REQ-ACCESS/history/verify", headers=rev
    ).json()
    assert history["valid"] is True and history["events"] == 3


def test_demo_endpoints_not_present_in_production(system):
    from src.platform.routes import create_router

    store, _, _ = system
    app = FastAPI()
    app.include_router(create_router(store))
    c = TestClient(app)
    assert (
        c.post("/api/v2/demo/session", json={"persona": "reviewer"}).status_code == 404
    )
    assert c.post("/api/v2/demo/process").status_code == 404


@pytest.mark.parametrize(
    "change",
    [
        {"filename": "../secret"},
        {"media_type": "application/executable"},
        {"content": ""},
    ],
)
def test_intake_validation_at_http_boundary(client, change):
    response = client.post(
        "/api/v2/requests/REQ-ACCESS/documents",
        json={**doc(), **change},
        headers={"Authorization": "Bearer owner-token", "Idempotency-Key": "invalid"},
    )
    assert response.status_code == 422


def test_missing_key_and_invented_role_are_rejected(client):
    assert (
        client.post(
            "/api/v2/requests/REQ-ACCESS/documents",
            json=doc(),
            headers={"Authorization": "Bearer owner-token"},
        ).status_code
        == 422
    )
    assert (
        client.post("/api/v2/demo/session", json={"persona": "admin"}).status_code
        == 422
    )
