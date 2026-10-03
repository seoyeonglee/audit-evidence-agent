from datetime import datetime, timedelta, timezone
from sqlalchemy import update
from src.enterprise.registry import RunRegistry
from src.enterprise.runner import GraphRunner
from src.enterprise.checkpoints import CheckpointManager
from src.enterprise.models import runs


def runner_fixture(f):
    store, _, users, _, _, root = f
    row = RunRegistry(store).start(
        users["reviewer"], "REQ-ACCESS", 2, "heuristic", "recovery"
    )
    clock = [datetime(2035, 1, 1, tzinfo=timezone.utc)]
    runner = GraphRunner(
        store,
        CheckpointManager(root / "cp"),
        "demo-acme",
        clock=lambda: clock[0],
        lease_seconds=1,
    )
    return store, users, row, clock, runner


def test_expired_lease_reclaimed_and_old_token_fenced(enterprise_fixture):
    store, users, row, clock, runner = runner_fixture(enterprise_fixture)
    first = runner._claim()
    clock[0] += timedelta(seconds=2)
    second = runner._claim()
    assert first["lease_token"] != second["lease_token"]
    assert runner._save(first, status="completed", report="{}") is False
    runner._execute(second)
    assert (
        RunRegistry(store).detail(users["reviewer"], row["id"])["status"]
        == "waiting_review"
    )


def test_retry_exhaustion_is_bounded_and_terminal(enterprise_fixture):
    store, users, row, clock, runner = runner_fixture(enterprise_fixture)
    with store.transaction("demo-acme") as conn:
        conn.execute(
            update(runs).where(runs.c.id == row["id"]).values(snapshot="invalid-json")
        )
    for attempt in range(3):
        assert runner.tick()
        clock[0] += timedelta(seconds=10)
    assert not runner.tick()
    with store.transaction("demo-acme") as conn:
        stored = (
            conn.execute(runs.select().where(runs.c.id == row["id"])).mappings().one()
        )
        assert stored["attempts"] == 3
        assert stored["status"] == "failed"
        assert stored["error"] == "JSONDecodeError"
