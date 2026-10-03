import pytest
from src.platform.database import Store
from src.platform.seed import seed_demo
from src.platform.service import EvidenceService
from src.platform.worker import Worker

GOOD = "system: production-admin\nperiod: 2026-Q3\nreviewed_users: 84\nexceptions: 0"


@pytest.fixture
def enterprise_fixture(tmp_path):
    store = Store(f"sqlite:///{tmp_path}/enterprise.db")
    store.migrate()
    tokens = seed_demo(store)
    service = EvidenceService(store)
    users = {k: service.authenticate(v) for k, v in tokens.items()}

    def submit(content=GOOD, key="source", request_id="REQ-ACCESS"):
        service.submit(
            users["owner"],
            request_id,
            key,
            {"filename": "access.txt", "media_type": "text/plain", "content": content},
        )
        Worker(store, "demo-acme").tick()

    submit()
    return store, service, users, tokens, submit, tmp_path
