import json
import uuid
from datetime import datetime, timedelta, timezone
from time import perf_counter
from filelock import FileLock, Timeout
from sqlalchemy import select, update, insert, or_, and_, func
from langgraph.types import Command
from src.platform.models import requests
from src.platform.service import packed, digest
from .models import runs, commands, run_events
from .graph import build_graph


class GraphRunner:
    def __init__(
        self, store, checkpoint_manager, tenant_id, clock=None, lease_seconds=60
    ):
        self.store, self.checkpoints, self.tenant_id = (
            store,
            checkpoint_manager,
            tenant_id,
        )
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.lease_seconds = lease_seconds

    def _now(self):
        return self.clock().isoformat()

    def _fence(self, run):
        return and_(
            runs.c.id == run["id"],
            runs.c.tenant_id == self.tenant_id,
            runs.c.lease_token == run["lease_token"],
            runs.c.status == "running",
            runs.c.lease_until > self._now(),
        )

    def _claim(self):
        with self.store.transaction(self.tenant_id) as conn:
            pending = select(commands.c.run_id).where(
                commands.c.tenant_id == self.tenant_id
            )
            eligible = or_(
                and_(runs.c.status == "queued", runs.c.available_at <= self._now()),
                and_(runs.c.status == "running", runs.c.lease_until <= self._now()),
                and_(runs.c.status == "waiting_review", runs.c.id.in_(pending)),
            )
            row = (
                conn.execute(
                    select(runs)
                    .where(runs.c.tenant_id == self.tenant_id, eligible)
                    .order_by(runs.c.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            row = dict(row)
            if row["attempts"] >= 3:
                conn.execute(
                    update(runs)
                    .where(runs.c.id == row["id"], runs.c.tenant_id == self.tenant_id)
                    .values(
                        status="failed",
                        error="RETRY_BUDGET_EXHAUSTED",
                        lease_token=None,
                        updated_at=self._now(),
                    )
                )
                return None
            token = uuid.uuid4().hex
            conn.execute(
                update(runs)
                .where(runs.c.id == row["id"], runs.c.tenant_id == self.tenant_id)
                .values(
                    status="running",
                    lease_token=token,
                    lease_until=(
                        self.clock() + timedelta(seconds=self.lease_seconds)
                    ).isoformat(),
                    attempts=row["attempts"] + 1,
                    updated_at=self._now(),
                )
            )
            return {**row, "lease_token": token, "attempts": row["attempts"] + 1}

    def _event(self, run, node, outcome, duration, value):
        with self.store.transaction(self.tenant_id) as conn:
            if not conn.execute(
                select(runs.c.id).where(self._fence(run)).with_for_update()
            ).first():
                raise RuntimeError("LeaseLost")
            sequence = (
                conn.execute(
                    select(func.max(run_events.c.sequence)).where(
                        run_events.c.tenant_id == self.tenant_id,
                        run_events.c.run_id == run["id"],
                    )
                ).scalar()
                or 0
            ) + 1
            conn.execute(
                insert(run_events).values(
                    tenant_id=self.tenant_id,
                    run_id=run["id"],
                    sequence=sequence,
                    node=node,
                    outcome=outcome,
                    duration_ms=max(0, int(duration * 1000)),
                    output_digest=digest(packed(value)),
                    created_at=self._now(),
                )
            )
            conn.execute(
                update(runs)
                .where(self._fence(run))
                .values(
                    lease_until=(
                        self.clock() + timedelta(seconds=self.lease_seconds)
                    ).isoformat()
                )
            )

    def tick(self):
        # One tenant checkpoint file, one host: exclude overlapping graph writers
        # even if a slow execution outlives its relational lease.
        lock = FileLock(str(self.checkpoints.path(self.tenant_id)) + ".lock", timeout=0)
        try:
            with lock:
                run = self._claim()
                if not run:
                    return False
                self._execute(run)
                return True
        except Timeout:
            return False

    def _execute(self, run):
        try:
            with self.store.transaction(self.tenant_id) as conn:
                command = (
                    conn.execute(
                        select(commands).where(
                            commands.c.tenant_id == self.tenant_id,
                            commands.c.run_id == run["id"],
                        )
                    )
                    .mappings()
                    .first()
                )
                current = conn.execute(
                    select(requests.c.version).where(
                        requests.c.tenant_id == self.tenant_id,
                        requests.c.id == run["request_id"],
                    )
                ).scalar_one()
            if not command and current != run["snapshot_version"]:
                self._save(run, status="superseded", error="SOURCE_VERSION_CHANGED")
                return
            safe_command = {
                k: v
                for k, v in dict(command or {}).items()
                if k not in {"key", "payload_hash"}
            }
            config = {"configurable": {"thread_id": run["id"]}, "recursion_limit": 20}
            with self.checkpoints.open(self.tenant_id) as saver:
                graph = build_graph(saver, run["provider"])
                state = graph.get_state(config)
                if state.values.get("report"):
                    result = state.values
                else:
                    if command:
                        if not state.values or not state.next:
                            raise RuntimeError("MissingReviewCheckpoint")
                        input_value = Command(resume=safe_command)
                    else:
                        input_value = (
                            None
                            if state.values
                            else {
                                "run_id": run["id"],
                                "snapshot": json.loads(run["snapshot"]),
                            }
                        )
                    start = perf_counter()
                    for event in graph.stream(
                        input_value, config, stream_mode="updates"
                    ):
                        for node, value in event.items():
                            if node == "__interrupt__":
                                self._event(
                                    run,
                                    "human_review",
                                    "waiting_review",
                                    perf_counter() - start,
                                    {"run_id": run["id"]},
                                )
                            else:
                                self._event(
                                    run, node, "complete", perf_counter() - start, value
                                )
                            start = perf_counter()
                    result = graph.get_state(config).values
            if result.get("report"):
                self._save(
                    run,
                    status="completed",
                    report=packed(result["report"]),
                    assessment=packed(result["assessment"]),
                    grounding=packed(result["grounding"]),
                )
            else:
                self._save(
                    run,
                    status="waiting_review",
                    assessment=packed(result["assessment"]),
                    grounding=packed(result["grounding"]),
                    attempts=0,
                )
        except Exception as error:
            self._save(
                run,
                status="failed" if run["attempts"] >= 3 else "queued",
                error=type(error).__name__,
                available_at=(
                    self.clock() + timedelta(seconds=2 ** run["attempts"])
                ).isoformat(),
            )

    def _save(self, run, **values):
        with self.store.transaction(self.tenant_id) as conn:
            return (
                conn.execute(
                    update(runs)
                    .where(self._fence(run))
                    .values(**values, lease_token=None, updated_at=self._now())
                ).rowcount
                == 1
            )
