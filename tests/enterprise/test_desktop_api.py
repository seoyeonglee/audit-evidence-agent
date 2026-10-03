import pytest
from fastapi.testclient import TestClient
from src.enterprise.desktop_api import create_desktop_app


def test_transport_secret_protects_every_route_and_does_not_replace_identity():
    secret = "s" * 64
    client = TestClient(create_desktop_app(secret))
    for route in [
        "/desktop/health",
        "/api/v2/requests",
        "/api/v2/demo/session",
        "/docs",
    ]:
        assert client.get(route).status_code == 403
        assert client.get(route, headers={"X-Desktop-Secret": "bad"}).status_code == 403
    assert (
        client.get("/desktop/health", headers={"X-Desktop-Secret": secret}).status_code
        == 200
    )
    assert (
        client.get("/api/v2/requests", headers={"X-Desktop-Secret": secret}).status_code
        == 401
    )
    with pytest.raises(RuntimeError):
        create_desktop_app("short")
