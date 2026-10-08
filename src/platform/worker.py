"""Leased database queue. Tenant-scoped workers run independently of HTTP requests."""

import argparse
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import signal
import time
import uuid

from sqlalchemy import and_, or_, select, update

from .auth import Principal
from .database import Store
from .extraction import PermanentError, canonical_record, extract
from .models import documents, jobs, requests, revisions
from .service import append_event, packed

logger = logging.getLogger("evidence.worker")


class Worker:
    def __init__(self, store, tenant_id, clock=None, lease_seconds=30, max_attempts=3):
        self.store, self.tenant_id = store, tenant_id
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.lease_seconds, self.max_attempts = lease_seconds, max_attempts
        self.principal = Principal(
            "document-worker", tenant_id, "auditor", "Document worker"
        )

    def claim(self):
        timestamp = self.clock().isoformat()
        eligible = or_(
            and_(jobs.c.status == "queued", jobs.c.available_at <= timestamp),
            and_(jobs.c.status == "running", jobs.c.lease_until <= timestamp),
        )
        with self.store.transaction(self.tenant_id) as conn:
            # SKIP LOCKED provides parallelism without multiple claims for one row.
            row = (
                conn.execute(
                    select(jobs)
                    .where(jobs.c.tenant_id == self.tenant_id, eligible)
                    .order_by(jobs.c.created_at, jobs.c.id)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            row = dict(row)
            token = uuid.uuid4().hex
            if row["attempts"] >= self.max_attempts:
                # Crash after the last claim is still terminalized by the next worker.
                conn.execute(
                    select(requests)
                    .where(
                        requests.c.id == row["request_id"],
                        requests.c.tenant_id == self.tenant_id,
                    )
                    .with_for_update()
                )
                conn.execute(
                    update(jobs)
                    .where(jobs.c.id == row["id"], jobs.c.tenant_id == self.tenant_id)
                    .values(
                        status="dead_letter",
                        finished_at=timestamp,
                        error="LeaseBudgetExhausted",
                        lease_token=None,
                    )
                )
                self._terminal(conn, row, "LeaseBudgetExhausted")
                return None
            result = conn.execute(
                update(jobs)
                .where(
                    jobs.c.id == row["id"], jobs.c.tenant_id == self.tenant_id, eligible
                )
                .values(
                    status="running",
                    attempts=row["attempts"] + 1,
                    lease_token=token,
                    lease_until=(
                        self.clock() + timedelta(seconds=self.lease_seconds)
                    ).isoformat(),
                )
            )
            if result.rowcount != 1:
                return None
            return {
                **row,
                "status": "running",
                "attempts": row["attempts"] + 1,
                "lease_token": token,
            }

    def _fence(self, job):
        return and_(
            jobs.c.id == job["id"],
            jobs.c.tenant_id == self.tenant_id,
            jobs.c.status == "running",
            jobs.c.lease_token == job["lease_token"],
            jobs.c.lease_until > self.clock().isoformat(),
        )

    def complete(self, job, extraction):
        with self.store.transaction(self.tenant_id) as conn:
            if not conn.execute(
                select(jobs.c.id).where(self._fence(job)).with_for_update()
            ).first():
                return False
            record = (
                conn.execute(
                    select(requests)
                    .where(
                        requests.c.id == job["request_id"],
                        requests.c.tenant_id == self.tenant_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .one()
            )
            result = conn.execute(
                update(jobs)
                .where(self._fence(job))
                .values(
                    status="succeeded",
                    finished_at=self.clock().isoformat(),
                    lease_token=None,
                    error=None,
                )
            )
            if result.rowcount != 1:
                return False
            if record["status"] == "approved":
                raise PermanentError("Approved records cannot be changed by a worker")
            conn.execute(
                update(documents)
                .where(
                    documents.c.id == job["document_id"],
                    documents.c.tenant_id == self.tenant_id,
                )
                .values(extraction=packed(extraction))
            )
            all_results = conn.execute(
                select(documents.c.extraction)
                .where(
                    documents.c.request_id == job["request_id"],
                    documents.c.tenant_id == self.tenant_id,
                    documents.c.extraction.is_not(None),
                    documents.c.id.not_in(
                        select(revisions.c.previous_id).where(
                            revisions.c.tenant_id == self.tenant_id
                        )
                    ),
                )
                .order_by(documents.c.created_at, documents.c.id)
            ).scalars()
            canonical = canonical_record(
                [json.loads(r) for r in all_results],
                record["period"],
                record["control_id"],
            )
            remaining = (
                conn.execute(
                    select(jobs.c.status).where(
                        jobs.c.tenant_id == self.tenant_id,
                        jobs.c.request_id == job["request_id"],
                        jobs.c.status != "succeeded",
                        jobs.c.document_id.not_in(
                            select(revisions.c.previous_id).where(
                                revisions.c.tenant_id == self.tenant_id
                            )
                        ),
                    )
                )
                .scalars()
                .all()
            )
            if "dead_letter" in remaining:
                canonical["exceptions"].append(
                    {
                        "code": "PROCESSING_FAILED",
                        "message": "A source document requires manual handling",
                    }
                )
                canonical["complete"] = False
            status = (
                "processing"
                if any(s in {"queued", "running"} for s in remaining)
                else "ready"
            )
            conn.execute(
                update(requests)
                .where(
                    requests.c.id == job["request_id"],
                    requests.c.tenant_id == self.tenant_id,
                )
                .values(
                    canonical=packed(canonical),
                    status=status,
                    version=record["version"] + 1,
                    updated_at=self.clock().isoformat(),
                )
            )
            append_event(
                conn,
                self.principal,
                job["request_id"],
                "document.processed",
                {
                    "document_id": job["document_id"],
                    "job_id": job["id"],
                    "attempt": job["attempts"],
                    "provider": extraction["provider"],
                    "exception_codes": [e["code"] for e in canonical["exceptions"]],
                },
            )
            logger.info(
                packed(
                    {
                        "event": "document.processed",
                        "job_id": job["id"],
                        "tenant_id": self.tenant_id,
                        "attempt": job["attempts"],
                    }
                )
            )
            return True

    def _terminal(self, conn, job, error):
        record = (
            conn.execute(
                select(requests).where(
                    requests.c.id == job["request_id"],
                    requests.c.tenant_id == self.tenant_id,
                )
            )
            .mappings()
            .one()
        )
        canonical = json.loads(record["canonical"])
        canonical["complete"] = False
        canonical.setdefault("exceptions", []).append(
            {
                "code": "PROCESSING_FAILED",
                "message": "A source document requires manual handling",
            }
        )
        conn.execute(
            update(requests)
            .where(
                requests.c.id == job["request_id"],
                requests.c.tenant_id == self.tenant_id,
            )
            .values(
                status="needs_changes",
                canonical=packed(canonical),
                version=requests.c.version + 1,
                updated_at=self.clock().isoformat(),
            )
        )
        append_event(
            conn,
            self.principal,
            job["request_id"],
            "document.dead_letter",
            {"job_id": job["id"], "error_type": error, "attempt": job["attempts"]},
        )

    def fail(self, job, error):
        terminal = (
            isinstance(error, PermanentError) or job["attempts"] >= self.max_attempts
        )
        error_type = type(
            error
        ).__name__  # never store uploaded contents or credentials in errors
        with self.store.transaction(self.tenant_id) as conn:
            if not conn.execute(
                select(jobs.c.id).where(self._fence(job)).with_for_update()
            ).first():
                return False
            conn.execute(
                select(requests)
                .where(
                    requests.c.id == job["request_id"],
                    requests.c.tenant_id == self.tenant_id,
                )
                .with_for_update()
            )
            result = conn.execute(
                update(jobs)
                .where(self._fence(job))
                .values(
                    status="dead_letter" if terminal else "queued",
                    error=error_type,
                    lease_token=None,
                    finished_at=self.clock().isoformat() if terminal else None,
                    available_at=(
                        self.clock() + timedelta(seconds=2 ** job["attempts"])
                    ).isoformat(),
                )
            )
            if result.rowcount != 1:
                return False
            if terminal:
                self._terminal(conn, job, error_type)
            else:
                append_event(
                    conn,
                    self.principal,
                    job["request_id"],
                    "document.retry_scheduled",
                    {
                        "job_id": job["id"],
                        "attempt": job["attempts"],
                        "error_type": error_type,
                    },
                )
            return True

    def tick(self):
        job = self.claim()
        if not job:
            return False
        try:
            with self.store.transaction(self.tenant_id) as conn:
                document = dict(
                    conn.execute(
                        select(documents).where(
                            documents.c.id == job["document_id"],
                            documents.c.tenant_id == self.tenant_id,
                        )
                    )
                    .mappings()
                    .one()
                )
            self.complete(job, extract(document))
        except Exception as error:
            self.fail(job, error)
        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    store = Store(os.environ.get("DATABASE_URL", "sqlite:///evidence-operations.db"))
    worker = Worker(store, args.tenant)
    stopping = [False]

    def stop(*_):
        stopping[0] = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logging.basicConfig(level=logging.INFO)
    while not stopping[0]:
        processed = worker.tick()
        if args.once:
            break
        if not processed:
            time.sleep(0.5)


if __name__ == "__main__":
    main()
