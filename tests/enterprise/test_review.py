import concurrent.futures
import pytest
from src.enterprise.registry import RunRegistry
from src.platform.service import DomainError


def paused(f):
    from src.enterprise.runner import GraphRunner
    from src.enterprise.checkpoints import CheckpointManager

    store, svc, users, _, _, root = f
    registry = RunRegistry(store)
    version = svc.detail(users["reviewer"], "REQ-ACCESS")["version"]
    run = registry.start(users["reviewer"], "REQ-ACCESS", version, "heuristic", "run")
    runner = GraphRunner(store, CheckpointManager(root / "cp"), "demo-acme")
    assert runner.tick()
    assert registry.detail(users["reviewer"], run["id"])["status"] == "waiting_review"
    return registry, run, runner


def test_crash_after_review_before_resume_is_recoverable(enterprise_fixture):
    from src.enterprise.review import review_run
    from src.enterprise.runner import GraphRunner

    registry, run, runner = paused(enterprise_fixture)
    store, svc, users, *_ = enterprise_fixture
    a = review_run(
        store,
        users["reviewer"],
        run["id"],
        run["snapshot_version"],
        "approve",
        "Verified source spans",
        "review-key",
    )
    b = review_run(
        store,
        users["reviewer"],
        run["id"],
        run["snapshot_version"],
        "approve",
        "Verified source spans",
        "review-key",
    )
    assert a["id"] == b["id"]
    assert svc.detail(users["reviewer"], "REQ-ACCESS")["status"] == "approved"
    recovered = GraphRunner(store, runner.checkpoints, "demo-acme")
    assert recovered.tick()
    detail = registry.detail(users["reviewer"], run["id"])
    assert detail["status"] == "completed"
    assert detail["report"]["review"]["id"] == a["id"]
    assert not recovered.tick()
    record = svc.detail(users["reviewer"], "REQ-ACCESS")
    assert sum(e["event_type"] == "review.approve" for e in record["events"]) == 1
    assert svc.verify_history(users["reviewer"], "REQ-ACCESS")["valid"]


@pytest.mark.parametrize(
    "persona,status",
    [("owner", 403), ("vendor", 404), ("auditor", 403), ("other-reviewer", 404)],
)
def test_review_denied_to_wrong_identity(enterprise_fixture, persona, status):
    from src.enterprise.review import review_run

    _, run, _ = paused(enterprise_fixture)
    with pytest.raises(DomainError) as error:
        review_run(
            enterprise_fixture[0],
            enterprise_fixture[2][persona],
            run["id"],
            run["snapshot_version"],
            "approve",
            "",
            "deny",
        )
    assert error.value.status == status


def test_changed_evidence_blocks_stale_review(enterprise_fixture):
    from src.enterprise.review import review_run

    registry, run, _ = paused(enterprise_fixture)
    enterprise_fixture[4](key="changed")
    with pytest.raises(DomainError) as error:
        review_run(
            enterprise_fixture[0],
            enterprise_fixture[2]["reviewer"],
            run["id"],
            run["snapshot_version"],
            "approve",
            "",
            "stale",
        )
    assert error.value.status == 409
    assert registry.detail(enterprise_fixture[2]["reviewer"], run["id"])["stale"]


def test_problem_evidence_requires_changes(enterprise_fixture):
    from src.enterprise.review import review_run

    enterprise_fixture[4](
        "system: alternate\nperiod: 2026-Q2\nexceptions: 2", "problem"
    )
    registry, run, runner = paused(enterprise_fixture)
    with pytest.raises(DomainError):
        review_run(
            enterprise_fixture[0],
            enterprise_fixture[2]["reviewer"],
            run["id"],
            run["snapshot_version"],
            "approve",
            "",
            "invalid",
        )
    review_run(
        enterprise_fixture[0],
        enterprise_fixture[2]["reviewer"],
        run["id"],
        run["snapshot_version"],
        "needs_changes",
        "Please resolve conflicting period",
        "changes",
    )
    assert runner.tick()
    assert (
        registry.detail(enterprise_fixture[2]["reviewer"], run["id"])["report"][
            "review"
        ]["decision"]
        == "needs_changes"
    )


def test_concurrent_reviews_have_one_canonical_event(enterprise_fixture):
    from src.enterprise.review import review_run

    _, run, _ = paused(enterprise_fixture)
    store, svc, users, *_ = enterprise_fixture

    def send(_):
        return review_run(
            store,
            users["reviewer"],
            run["id"],
            run["snapshot_version"],
            "approve",
            "same",
            "race",
        )["id"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(send, range(5)))
    assert len(set(results)) == 1
    assert (
        sum(
            e["event_type"] == "review.approve"
            for e in svc.detail(users["reviewer"], "REQ-ACCESS")["events"]
        )
        == 1
    )
    with pytest.raises(DomainError) as error:
        review_run(
            store,
            users["reviewer"],
            run["id"],
            run["snapshot_version"],
            "reject",
            "changed",
            "race",
        )
    assert error.value.status == 409
