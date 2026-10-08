from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json

import pytest
from sqlalchemy import select
from tests.platform.test_workflow import system as system, doc
from src.platform.service import DomainError


def collaboration(system):
    from src.platform.collaboration import CollaborationService

    return CollaborationService(system[0])


def test_invitation_scoped_submission_and_one_time_accept(system):
    _, service, users = system
    c = collaboration(system)
    invite = c.create_invitation(users["reviewer"], "REQ-ACCESS")
    assert (
        86390
        < (
            datetime.fromisoformat(invite["expires_at"]) - datetime.now(timezone.utc)
        ).total_seconds()
        <= 86400
    )
    accepted = c.accept_invitation(invite["token"], "External contributor")
    user = service.authenticate(accepted["token"])
    assert [r["id"] for r in service.list_requests(user)] == ["REQ-ACCESS"]
    service.submit(user, "REQ-ACCESS", "external", doc())
    with pytest.raises(DomainError):
        service.detail(user, "REQ-VENDOR")
    with pytest.raises(DomainError):
        service.review(user, "REQ-ACCESS", 1, "approve", "")
    with pytest.raises(DomainError):
        c.accept_invitation(invite["token"], "Again")
    history = service.detail(users["reviewer"], "REQ-ACCESS")["events"]
    assert invite["token"] not in json.dumps(history)
    assert accepted["token"] not in json.dumps(history)


def test_revoke_disables_existing_session_and_old_principal(system):
    _, service, users = system
    c = collaboration(system)
    invite = c.create_invitation(users["reviewer"], "REQ-ACCESS")
    token = c.accept_invitation(invite["token"], "Vendor")["token"]
    user = service.authenticate(token)
    c.revoke_invitation(users["reviewer"], "REQ-ACCESS", invite["id"])
    with pytest.raises(DomainError):
        service.authenticate(token)
    with pytest.raises(DomainError):
        service.submit(user, "REQ-ACCESS", "after-revoke", doc())


def test_expiry_and_tampered_locator_fail(system):
    _, service, users = system
    c = collaboration(system)
    invite = c.create_invitation(users["reviewer"], "REQ-ACCESS")
    c.clock = lambda: datetime.now(timezone.utc) + timedelta(days=2)
    with pytest.raises(DomainError):
        c.accept_invitation(invite["token"], "Expired")
    c.clock = lambda: datetime.now(timezone.utc)
    parts = invite["token"].split(".")
    parts[1] = "ZGVtby1vdGhlcg"
    with pytest.raises(DomainError):
        c.accept_invitation(".".join(parts), "Wrong tenant")
    session = c.accept_invitation(invite["token"], "Vendor")
    parts = session["token"].split(".")
    parts[1] = "ZGVtby1vdGhlcg"
    with pytest.raises(DomainError):
        service.authenticate(".".join(parts))


def test_simultaneous_accept_only_one_session(system):
    c = collaboration(system)
    invite = c.create_invitation(system[2]["reviewer"], "REQ-ACCESS")

    def accept(_):
        try:
            return c.accept_invitation(invite["token"], "Vendor")
        except DomainError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(accept, range(4)))
    assert len([x for x in results if x]) == 1


@pytest.mark.parametrize("hours", [0, -1, 169])
def test_invalid_ttl(system, hours):
    with pytest.raises(DomainError) as e:
        collaboration(system).create_invitation(
            system[2]["reviewer"], "REQ-ACCESS", hours
        )
    assert e.value.status == 422


def test_only_reviewer_can_invite(system):
    with pytest.raises(DomainError) as e:
        collaboration(system).create_invitation(system[2]["owner"], "REQ-ACCESS")
    assert e.value.status == 403


def test_database_stores_hashes_not_raw_tokens(system):
    from src.platform.models import invitations, external_sessions

    c = collaboration(system)
    invite = c.create_invitation(system[2]["reviewer"], "REQ-ACCESS")
    session = c.accept_invitation(invite["token"], "Vendor")
    with system[0].transaction("demo-acme") as conn:
        stored = str(list(conn.execute(select(invitations)).mappings())) + str(
            list(conn.execute(select(external_sessions)).mappings())
        )
    assert invite["token"] not in stored
    assert session["token"] not in stored
