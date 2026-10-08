from tests.platform.test_api import client as client, system as system
from tests.platform.test_workflow import doc


def test_invite_http_scope_cache_and_revoke(client):
    reviewer = {"Authorization": "Bearer reviewer-token"}
    response = client.post(
        "/api/v2/requests/REQ-ACCESS/invitations", headers=reviewer, json={}
    )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    invite = response.json()
    assert client.get(
        "/api/v2/invitations/accept", params={"token": invite["token"]}
    ).status_code in (404, 405)
    accepted = client.post(
        "/api/v2/invitations/accept",
        json={"token": invite["token"], "name": "Supplier"},
    )
    assert accepted.status_code == 200
    external = {"Authorization": "Bearer " + accepted.json()["token"]}
    assert client.get("/api/v2/session", headers=external).json()["external"]
    assert (
        client.get("/api/v2/requests/REQ-VENDOR", headers=external).status_code == 404
    )
    assert (
        client.post(
            "/api/v2/requests/REQ-ACCESS/invitations", headers=external, json={}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v2/requests/REQ-ACCESS/invitations/" + invite["id"] + "/revoke",
            headers=reviewer,
            json={},
        ).status_code
        == 200
    )
    assert client.get("/api/v2/requests", headers=external).status_code == 401


def test_accept_attempts_are_persistently_limited(client):
    for _ in range(10):
        assert (
            client.post(
                "/api/v2/invitations/accept",
                json={"token": "invite.bad." + "x" * 43, "name": "Test"},
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/v2/invitations/accept",
            json={"token": "invite.bad." + "x" * 43, "name": "Test"},
        ).status_code
        == 429
    )


def test_revisions_http_workflow(client):
    owner = {"Authorization": "Bearer owner-token", "Idempotency-Key": "first"}
    reviewer = {"Authorization": "Bearer reviewer-token"}
    first = client.post(
        "/api/v2/requests/REQ-ACCESS/documents", headers=owner, json=doc()
    ).json()
    client.post("/api/v2/demo/process", headers=reviewer, json={})
    detail = client.get("/api/v2/requests/REQ-ACCESS", headers=reviewer).json()
    client.post(
        "/api/v2/requests/REQ-ACCESS/review",
        headers=reviewer,
        json={"version": detail["version"], "decision": "approve"},
    )
    approved = client.get("/api/v2/requests/REQ-ACCESS", headers=reviewer).json()
    reopened = client.post(
        "/api/v2/requests/REQ-ACCESS/reopen",
        headers=reviewer,
        json={"version": approved["version"], "reason": "Correction"},
    )
    assert reopened.status_code == 200
    response = client.post(
        "/api/v2/requests/REQ-ACCESS/documents",
        headers={**owner, "Idempotency-Key": "second"},
        json={**doc(), "replaces_document_id": first["document_id"]},
    )
    assert response.status_code == 202
    client.post("/api/v2/demo/process", headers=reviewer, json={})
    detail = client.get("/api/v2/requests/REQ-ACCESS", headers=reviewer).json()
    assert any(d["superseded_by"] for d in detail["documents"])
