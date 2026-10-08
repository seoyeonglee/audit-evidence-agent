"""Upgrade a pre-collaboration database without resetting approved evidence."""

from sqlalchemy import MetaData, select, update
from src.platform.database import Store
from src.platform.models import metadata, requests, documents, jobs
from src.platform.seed import seed_demo
from src.platform.service import EvidenceService, append_event, packed
from src.platform.extraction import canonical_record, extract
from tests.platform.test_workflow import doc


def test_additive_upgrade_preserves_existing_approval(tmp_path):
    store = Store(f"sqlite:///{tmp_path}/old.db")
    old = MetaData()
    for name in ["members", "requests", "documents", "jobs", "audit_events"]:
        metadata.tables[name].to_metadata(old)
    for index in list(old.tables["documents"].indexes):
        if index.name == "uq_document_request_identity":
            old.tables["documents"].indexes.remove(index)
    old.create_all(store.engine)
    tokens = seed_demo(store)
    service = EvidenceService(store)
    owner = service.authenticate(tokens["owner"])
    reviewer = service.authenticate(tokens["reviewer"])
    submitted = service.submit(owner, "REQ-ACCESS", "legacy", doc())
    with store.transaction("demo-acme") as conn:
        source = dict(
            conn.execute(
                select(documents).where(documents.c.id == submitted["document_id"])
            )
            .mappings()
            .one()
        )
        extraction = extract(source)
        conn.execute(
            update(documents)
            .where(documents.c.id == source["id"])
            .values(extraction=packed(extraction))
        )
        conn.execute(
            update(jobs)
            .where(jobs.c.id == submitted["job_id"])
            .values(status="succeeded")
        )
        conn.execute(
            update(requests)
            .where(requests.c.id == "REQ-ACCESS")
            .values(
                status="approved",
                version=3,
                canonical=packed(canonical_record([extraction], "2026-Q3")),
            )
        )
        append_event(
            conn,
            reviewer,
            "REQ-ACCESS",
            "review.approve",
            {"version": 2, "feedback": "Legacy approved record"},
        )
        before = {
            name: [
                dict(r) for r in conn.execute(select(metadata.tables[name])).mappings()
            ]
            for name in ["requests", "documents", "jobs", "audit_events"]
        }
    store.migrate()
    store.migrate()
    with store.transaction("demo-acme") as conn:
        after = {
            name: [
                dict(r) for r in conn.execute(select(metadata.tables[name])).mappings()
            ]
            for name in before
        }
    assert after == before
    record = service.detail(reviewer, "REQ-ACCESS")
    assert record["status"] == "approved"
    assert record["documents"][0]["superseded_by"] is None
    assert service.verify_history(reviewer, "REQ-ACCESS")["valid"]
