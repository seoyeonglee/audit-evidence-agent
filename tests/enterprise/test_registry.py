import pytest
from sqlalchemy import update
from src.platform.models import requests
from src.platform.service import DomainError


def start(f):
    from src.enterprise.registry import RunRegistry

    store, svc, users, *_ = f
    registry = RunRegistry(store)
    version = svc.detail(users["reviewer"], "REQ-ACCESS")["version"]
    return registry, registry.start(
        users["reviewer"], "REQ-ACCESS", version, "heuristic", "start"
    )


def test_start_snapshot_is_immutable(enterprise_fixture):
    registry, run = start(enterprise_fixture)
    _, _, users, _, submit, _ = enterprise_fixture
    submit(
        "system: different\nperiod: 2026-Q3\nreviewed_users: 84\nexceptions: 0", "next"
    )
    old = registry.detail(users["reviewer"], run["id"])
    assert (
        old["snapshot"]["canonical"]["fields"]["system"]["value"] == "production-admin"
    )
    assert len(old["snapshot"]["documents"]) == 1


def test_duplicate_start_returns_same_run(enterprise_fixture):
    registry, run = start(enterprise_fixture)
    user = enterprise_fixture[2]["reviewer"]
    replay = registry.start(
        user, "REQ-ACCESS", run["snapshot_version"], "heuristic", "start"
    )
    assert replay["id"] == run["id"]
    other_key = registry.start(
        user, "REQ-ACCESS", run["snapshot_version"], "heuristic", "another-key"
    )
    assert other_key["id"] == run["id"]
    with pytest.raises(DomainError) as error:
        registry.start(
            user, "REQ-ACCESS", run["snapshot_version"] + 1, "heuristic", "start"
        )
    assert error.value.status == 409


@pytest.mark.parametrize(
    "persona,status", [("owner", 403), ("vendor", 403), ("other-reviewer", 404)]
)
def test_start_checks_role_scope(enterprise_fixture, persona, status):
    registry, run = start(enterprise_fixture)
    with pytest.raises(DomainError) as error:
        registry.start(
            enterprise_fixture[2][persona],
            "REQ-ACCESS",
            run["snapshot_version"],
            "heuristic",
            "bad",
        )
    assert error.value.status == status


def test_scope_checked_on_run_detail(enterprise_fixture):
    registry, run = start(enterprise_fixture)
    with pytest.raises(DomainError) as error:
        registry.detail(enterprise_fixture[2]["other-reviewer"], run["id"])
    assert error.value.status == 404


def test_limits_20_documents(enterprise_fixture):
    store, svc, users, _, submit, _ = enterprise_fixture
    for n in range(20):
        submit(key=f"doc-{n}")
    from src.enterprise.registry import RunRegistry

    with pytest.raises(DomainError) as error:
        RunRegistry(store).start(
            users["reviewer"],
            "REQ-ACCESS",
            svc.detail(users["reviewer"], "REQ-ACCESS")["version"],
            "heuristic",
            "too-many",
        )
    assert error.value.status == 422


def test_start_rejects_processing_and_approved(enterprise_fixture):
    store, svc, users, *_ = enterprise_fixture
    from src.enterprise.registry import RunRegistry

    for status in ["processing", "approved"]:
        with store.transaction("demo-acme") as conn:
            conn.execute(
                update(requests)
                .where(requests.c.id == "REQ-ACCESS")
                .values(status=status)
            )
        with pytest.raises(DomainError) as error:
            RunRegistry(store).start(
                users["reviewer"], "REQ-ACCESS", 2, "heuristic", status
            )
        assert error.value.status == 409
