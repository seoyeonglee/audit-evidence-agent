import pytest
from tests.platform.test_workflow import system as system, doc
from src.platform.service import DomainError
from src.platform.worker import Worker


def processed(system, content=None):
    store, service, users = system
    result = service.submit(
        users["owner"],
        "REQ-ACCESS",
        "first",
        doc() if content is None else doc(content),
    )
    Worker(store, "demo-acme").tick()
    return result


def test_revision_corrects_conflicts_and_retains_history(system):
    store, service, users = system
    first = processed(system)
    detail = service.detail(users["reviewer"], "REQ-ACCESS")
    service.review(
        users["reviewer"],
        "REQ-ACCESS",
        detail["version"],
        "needs_changes",
        "Update count",
    )
    replacement = doc(
        "system: production-admin\nperiod: 2026-Q3\nreviewed_users: 91\nexceptions: 0"
    )
    result = service.submit(
        users["owner"],
        "REQ-ACCESS",
        "revision",
        replacement,
        replaces_document_id=first["document_id"],
    )
    replay = service.submit(
        users["owner"],
        "REQ-ACCESS",
        "revision",
        replacement,
        replaces_document_id=first["document_id"],
    )
    assert replay["document_id"] == result["document_id"] and replay["replayed"]
    Worker(store, "demo-acme").tick()
    detail = service.detail(users["reviewer"], "REQ-ACCESS")
    assert len(detail["documents"]) == 2
    assert detail["canonical"]["fields"]["reviewed_users"]["value"] == 91
    assert not detail["canonical"]["exceptions"]
    old = next(d for d in detail["documents"] if d["id"] == first["document_id"])
    assert old["superseded_by"] == result["document_id"]
    assert detail["documents"][-1]["extraction"] is not None
    approved = service.review(
        users["reviewer"],
        "REQ-ACCESS",
        detail["version"],
        "approve",
        "Verified new count",
    )
    assert approved["status"] == "approved"
    assert service.verify_history(users["reviewer"], "REQ-ACCESS")["valid"]


def test_reopen_requires_fresh_independent_review(system):
    store, service, users = system
    first = processed(system)
    detail = service.detail(users["reviewer"], "REQ-ACCESS")
    approved = service.review(
        users["reviewer"], "REQ-ACCESS", detail["version"], "approve", "First approval"
    )
    with pytest.raises(DomainError):
        service.submit(
            users["owner"],
            "REQ-ACCESS",
            "illegal",
            doc(),
            replaces_document_id=first["document_id"],
        )
    reopened = service.reopen(
        users["reviewer"], "REQ-ACCESS", approved["version"], "Quarterly correction"
    )
    assert reopened["status"] == "needs_changes"
    with pytest.raises(DomainError):
        service.review(
            users["reviewer"],
            "REQ-ACCESS",
            reopened["version"],
            "approve",
            "No new evidence",
        )
    service.submit(
        users["owner"],
        "REQ-ACCESS",
        "second",
        doc(),
        replaces_document_id=first["document_id"],
    )
    Worker(store, "demo-acme").tick()
    current = service.detail(users["reviewer"], "REQ-ACCESS")
    final = service.review(
        users["reviewer"],
        "REQ-ACCESS",
        current["version"],
        "approve",
        "Second approval",
    )
    assert len([e for e in final["events"] if e["event_type"] == "review.approve"]) == 2


def test_pending_and_superseded_replacements_rejected(system):
    store, service, users = system
    first = service.submit(users["owner"], "REQ-ACCESS", "first", doc())
    with pytest.raises(DomainError) as e:
        service.submit(
            users["owner"],
            "REQ-ACCESS",
            "pending",
            doc(),
            replaces_document_id=first["document_id"],
        )
    assert e.value.status == 409
    Worker(store, "demo-acme").tick()
    service.submit(
        users["owner"],
        "REQ-ACCESS",
        "second",
        doc(),
        replaces_document_id=first["document_id"],
    )
    Worker(store, "demo-acme").tick()
    with pytest.raises(DomainError) as e:
        service.submit(
            users["owner"],
            "REQ-ACCESS",
            "fork",
            doc(),
            replaces_document_id=first["document_id"],
        )
    assert e.value.status == 409


def test_replacing_failed_document_unblocks_approval(system):
    store, service, users = system
    first = service.submit(
        users["owner"],
        "REQ-ACCESS",
        "bad",
        {
            "filename": "bad.json",
            "media_type": "application/json",
            "content": "{broken",
        },
    )
    Worker(store, "demo-acme").tick()
    service.submit(
        users["owner"],
        "REQ-ACCESS",
        "fixed",
        doc(),
        replaces_document_id=first["document_id"],
    )
    Worker(store, "demo-acme").tick()
    detail = service.detail(users["reviewer"], "REQ-ACCESS")
    assert detail["canonical"]["complete"] and not detail["canonical"]["exceptions"]


@pytest.mark.parametrize(
    "who,version,reason",
    [("owner", 2, "Reason"), ("reviewer", 0, "Reason"), ("reviewer", 2, "")],
)
def test_reopen_rejects_unauthorized_stale_or_empty(system, who, version, reason):
    processed(system)
    service, users = system[1:]
    detail = service.detail(users["reviewer"], "REQ-ACCESS")
    service.review(users["reviewer"], "REQ-ACCESS", detail["version"], "approve", "")
    with pytest.raises(DomainError):
        service.reopen(users[who], "REQ-ACCESS", version, reason)


def test_replacement_requires_same_request_and_existing_source(system):
    _, service, users = system
    processed(system)
    with pytest.raises(DomainError):
        service.submit(
            users["owner"],
            "REQ-ACCESS",
            "unknown",
            doc(),
            replaces_document_id="missing",
        )


def test_database_rejects_cross_request_revision(system):
    from sqlalchemy import insert
    from sqlalchemy.exc import DatabaseError
    from src.platform.models import revisions

    store, service, users = system
    first = processed(system)
    other = service.submit(users["auditor"], "REQ-BACKUP", "backup", doc())
    with pytest.raises(DatabaseError):
        with store.transaction("demo-acme") as conn:
            conn.execute(
                insert(revisions).values(
                    tenant_id="demo-acme",
                    request_id="REQ-ACCESS",
                    previous_id=first["document_id"],
                    replacement_id=other["document_id"],
                    created_at="2026-10-08",
                )
            )
