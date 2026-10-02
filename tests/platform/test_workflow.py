import concurrent.futures

import pytest
from sqlalchemy import update, delete


@pytest.fixture
def system(tmp_path):
    from src.platform.database import Store
    from src.platform.seed import seed_demo
    from src.platform.service import EvidenceService

    store = Store(f"sqlite:///{tmp_path}/workflow.db")
    store.migrate()
    tokens = seed_demo(store)
    service = EvidenceService(store)
    users = {name: service.authenticate(token) for name, token in tokens.items()}
    return store, service, users


def doc(
    content="system: production-admin\nperiod: 2026-Q3\nreviewed_users: 84\nexceptions: 0",
):
    return {
        "filename": "access-review.txt",
        "media_type": "text/plain",
        "content": content,
    }


def test_submission_persists_across_connections(system):
    from src.platform.service import EvidenceService
    from src.platform.database import Store

    store, service, users = system
    result = service.submit(users["owner"], "REQ-ACCESS", "k1", doc())
    other = EvidenceService(Store(store.url))
    record = other.detail(users["reviewer"], "REQ-ACCESS")
    assert record["status"] == "processing"
    assert record["documents"][0]["id"] == result["document_id"]
    assert record["jobs"][0]["status"] == "queued"
    assert record["events"][-1]["event_type"] == "document.submitted"


def test_duplicate_key_has_one_job_and_event(system):
    _, service, users = system
    a = service.submit(users["owner"], "REQ-ACCESS", "same", doc())
    b = service.submit(users["owner"], "REQ-ACCESS", "same", doc())
    assert a["job_id"] == b["job_id"]
    assert b["replayed"] is True
    record = service.detail(users["reviewer"], "REQ-ACCESS")
    assert len(record["jobs"]) == len(record["documents"]) == 1
    assert sum(e["event_type"] == "document.submitted" for e in record["events"]) == 1


def test_conflicting_idempotency_payload_is_rejected(system):
    from src.platform.service import DomainError

    _, service, users = system
    service.submit(users["owner"], "REQ-ACCESS", "same", doc())
    with pytest.raises(DomainError) as error:
        service.submit(users["owner"], "REQ-ACCESS", "same", doc("system: different"))
    assert error.value.status == 409


@pytest.mark.parametrize(
    "user,request_id",
    [
        ("other-reviewer", "REQ-ACCESS"),
        ("vendor", "REQ-ACCESS"),
        ("owner", "REQ-VENDOR"),
    ],
)
def test_request_scope_cannot_be_widened(system, user, request_id):
    from src.platform.service import DomainError

    _, service, users = system
    with pytest.raises(DomainError) as error:
        service.detail(users[user], request_id)
    assert error.value.status == 404


def test_vendor_sees_only_assigned_request(system):
    _, service, users = system
    assert [r["id"] for r in service.list_requests(users["vendor"])] == ["REQ-VENDOR"]


@pytest.mark.parametrize("user", ["owner", "vendor", "auditor"])
def test_non_reviewer_cannot_review(system, user):
    from src.platform.service import DomainError

    _, service, users = system
    with pytest.raises(DomainError) as error:
        service.review(users[user], "REQ-ACCESS", 0, "approve", "review")
    assert error.value.status == 403


def test_pending_record_cannot_be_approved(system):
    from src.platform.service import DomainError

    _, service, users = system
    with pytest.raises(DomainError) as error:
        service.review(users["reviewer"], "REQ-ACCESS", 0, "approve", "")
    assert error.value.status == 409


def test_stale_version_fails_without_appending_event(system):
    from src.platform.service import DomainError

    _, service, users = system
    service.submit(users["owner"], "REQ-ACCESS", "k1", doc())
    before = service.detail(users["reviewer"], "REQ-ACCESS")
    with pytest.raises(DomainError) as error:
        service.review(users["reviewer"], "REQ-ACCESS", 0, "needs_changes", "stale")
    assert error.value.status == 409
    assert len(service.detail(users["reviewer"], "REQ-ACCESS")["events"]) == len(
        before["events"]
    )


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_database_rejects_audit_event_mutation(system, operation):
    from src.platform.models import events
    from sqlalchemy.exc import DatabaseError

    store, service, users = system
    service.submit(users["owner"], "REQ-ACCESS", "k1", doc())
    with pytest.raises(DatabaseError):
        with store.transaction("demo-acme") as conn:
            statement = (
                update(events).values(event_type="forged")
                if operation == "update"
                else delete(events)
            )
            conn.execute(statement)
    assert service.verify_history(users["reviewer"], "REQ-ACCESS")["valid"] is True


def test_concurrent_duplicate_submission_is_atomic(system):
    _, service, users = system
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda _: service.submit(users["owner"], "REQ-ACCESS", "race", doc()),
                range(8),
            )
        )
    assert len({r["job_id"] for r in results}) == 1
    assert len(service.detail(users["reviewer"], "REQ-ACCESS")["jobs"]) == 1


def test_invalid_token_rejected(system):
    from src.platform.service import DomainError

    _, service, _ = system
    with pytest.raises(DomainError) as error:
        service.authenticate("invented")
    assert error.value.status == 401


@pytest.mark.parametrize("content", ["", "x" * 200001], ids=["empty", "oversized"])
def test_empty_and_oversized_document_rejected(system, content):
    from src.platform.service import DomainError

    _, service, users = system
    with pytest.raises(DomainError) as error:
        service.submit(users["owner"], "REQ-ACCESS", "bad", doc(content))
    assert error.value.status == 422
