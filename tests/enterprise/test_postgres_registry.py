"""Real PostgreSQL gates: run after the platform suite on its CI service."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import insert, text, update, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DatabaseError
from src.platform.database import Store
from src.platform.seed import seed_demo
from src.platform.service import EvidenceService, DomainError, now
from src.platform.worker import Worker
from src.platform.models import requests, events
from src.enterprise.registry import RunRegistry
from src.enterprise.runner import GraphRunner
from src.enterprise.checkpoints import CheckpointManager
from src.enterprise.review import review_run
from src.enterprise.models import commands, run_events

URL = os.environ.get("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Real TEST_POSTGRES_URL required")


@pytest.fixture(scope="module")
def pg_agent(tmp_path_factory):
    admin = Store(URL)
    admin.migrate()
    tokens = seed_demo(admin)
    with admin.engine.begin() as conn:
        conn.execute(
            text(
                "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='agent_test_app') THEN CREATE ROLE agent_test_app LOGIN PASSWORD 'test-only-password' NOSUPERUSER NOBYPASSRLS; END IF; END $$"
            )
        )
        conn.execute(text("GRANT USAGE ON SCHEMA public TO agent_test_app"))
        conn.execute(text("GRANT SELECT ON members TO agent_test_app"))
        conn.execute(
            text(
                "GRANT SELECT,INSERT,UPDATE,DELETE ON requests,documents,jobs,audit_events,agent_runs,agent_review_commands,agent_run_events TO agent_test_app"
            )
        )
        conn.execute(
            text(
                "GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO agent_test_app"
            )
        )
    store = Store(
        make_url(URL)
        .set(username="agent_test_app", password="test-only-password")
        .render_as_string(hide_password=False)
    )
    service = EvidenceService(store)
    users = {k: service.authenticate(v) for k, v in tokens.items()}
    manager = CheckpointManager(tmp_path_factory.mktemp("pg-checkpoints"))
    yield store, service, users, manager
    store.engine.dispose()
    admin.engine.dispose()


def fresh(f):
    store, svc, users, cp = f
    rid = "PG-" + uuid.uuid4().hex
    with store.transaction("demo-acme") as conn:
        conn.execute(
            insert(requests).values(
                id=rid,
                tenant_id="demo-acme",
                title="PG race",
                control_id="AC-01",
                owner_id="owner",
                period="2026-Q3",
                status="awaiting_evidence",
                version=0,
                canonical="{}",
                updated_at=now(),
            )
        )
    doc = {
        "filename": "review.txt",
        "media_type": "text/plain",
        "content": "system: production-admin\nperiod: 2026-Q3\nreviewed_users: 84\nexceptions: 0",
    }
    svc.submit(users["owner"], rid, uuid.uuid4().hex, doc)
    while Worker(store, "demo-acme").tick():
        pass
    run = RunRegistry(store).start(
        users["reviewer"], rid, 2, "heuristic", uuid.uuid4().hex
    )
    while GraphRunner(store, cp, "demo-acme").tick():
        pass
    return rid, run, doc


def test_registry_and_event_rls_non_bypass(pg_agent):
    store, _, users, _ = pg_agent
    rid, run, _ = fresh(pg_agent)
    review_run(
        store, users["reviewer"], run["id"], 2, "approve", "Verified", uuid.uuid4().hex
    )
    for table in ["agent_runs", "agent_review_commands", "agent_run_events"]:
        with store.transaction() as conn:
            assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
        with store.transaction("demo-north") as conn:
            assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
        with store.transaction("demo-acme") as conn:
            assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() > 0
            assert conn.execute(
                text(
                    "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
                )
            ).one() == (False, False)
    for table in [commands, run_events]:
        with pytest.raises(DatabaseError):
            with store.transaction("demo-acme") as conn:
                conn.execute(update(table).values(tenant_id="forged"))


def test_simultaneous_submit_review_order_and_duplicate_command(pg_agent):
    store, svc, users, cp = pg_agent
    rid, run, doc = fresh(pg_agent)

    def approve(key):
        try:
            return review_run(
                store, users["reviewer"], run["id"], 2, "approve", "Verified", key
            )
        except DomainError as error:
            return error.status

    def submit():
        try:
            return svc.submit(users["owner"], rid, uuid.uuid4().hex, doc)
        except DomainError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(approve, "race-" + rid), pool.submit(submit)
        results = [a.result(timeout=10), b.result(timeout=10)]
    assert sum(isinstance(r, dict) for r in results) == 1
    assert results.count(409) == 1
    rid2, run2, _ = fresh(pg_agent)
    with ThreadPoolExecutor(max_workers=6) as pool:
        receipts = list(
            pool.map(
                lambda _: review_run(
                    store,
                    users["reviewer"],
                    run2["id"],
                    2,
                    "approve",
                    "Verified",
                    "same-" + rid2,
                ),
                range(6),
            )
        )
    assert len({r["id"] for r in receipts}) == 1
    with store.transaction("demo-acme") as conn:
        rows = conn.execute(
            select(events).where(
                events.c.request_id == rid2, events.c.event_type == "review.approve"
            )
        ).all()
        assert len(rows) == 1
