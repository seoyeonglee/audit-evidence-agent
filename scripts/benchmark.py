"""Single-host ASGI/SQLite benchmark; raw timings retained, no cloud extrapolation."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import tempfile
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import insert

from src.platform.database import Store
from src.platform.models import requests
from src.platform.routes import create_router
from src.platform.seed import seed_demo
from src.platform.service import EvidenceService, now
from src.platform.worker import Worker


def percentile(values, p):
    return sorted(values)[max(0, int(len(values) * p) - 1)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=int, default=100)
    parser.add_argument("--documents-per-record", type=int, default=10)
    parser.add_argument("--reads", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--output", default="docs/reports/benchmark.json")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        store = Store(f"sqlite:///{folder}/benchmark.db")
        store.migrate()
        tokens = seed_demo(store)
        service = EvidenceService(store)
        owner = service.authenticate(tokens["owner"])
        with store.transaction("demo-acme") as conn:
            conn.execute(
                insert(requests),
                [
                    dict(
                        id=f"BENCH-{i:05}",
                        tenant_id="demo-acme",
                        title="Synthetic benchmark record",
                        control_id="AC-01",
                        owner_id="owner",
                        period="2026-Q3",
                        status="awaiting_evidence",
                        version=0,
                        canonical="{}",
                        updated_at=now(),
                    )
                    for i in range(args.records)
                ],
            )
        start = time.perf_counter()
        for i in range(args.records):
            for j in range(args.documents_per_record):
                service.submit(
                    owner,
                    f"BENCH-{i:05}",
                    f"{i}:{j}",
                    {
                        "filename": f"evidence-{j}.txt",
                        "media_type": "text/plain",
                        "content": "system: production-admin\nperiod: 2026-Q3\nreviewed_users: 84\nexceptions: 0",
                    },
                )
        intake_seconds = time.perf_counter() - start
        worker = Worker(store, "demo-acme")
        processed = 0
        start = time.perf_counter()
        while worker.tick():
            processed += 1
        processing_seconds = time.perf_counter() - start
        app = FastAPI()
        app.include_router(create_router(store))
        headers = {"Authorization": "Bearer " + tokens["reviewer"]}
        with TestClient(app) as client:
            for i in range(20):
                client.get(
                    f"/api/v2/requests/BENCH-{i % args.records:05}", headers=headers
                )

            def read(i):
                start = time.perf_counter()
                r = client.get(
                    f"/api/v2/requests/BENCH-{i % args.records:05}", headers=headers
                )
                return (time.perf_counter() - start) * 1000, r.status_code

            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                rows = list(pool.map(read, range(args.reads)))
            read_seconds = time.perf_counter() - started
        latencies = [r[0] for r in rows]
        records = service.list_requests(service.authenticate(tokens["reviewer"]))
        completed = sum(r["canonical"].get("complete", False) for r in records)
        report = {
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "backend": "SQLite WAL / SQLAlchemy",
            "transport": "FastAPI TestClient in-process ASGI; includes token lookup and serialized DB transactions",
            "provider": "deterministic-key-value-v1",
            "record_count": args.records,
            "document_jobs": processed,
            "documents_per_record": args.documents_per_record,
            "completed_records": completed,
            "read_requests": args.reads,
            "read_concurrency": args.concurrency,
            "read_errors": sum(code != 200 for _, code in rows),
            "read_p50_ms": percentile(latencies, 0.50),
            "read_p95_ms": percentile(latencies, 0.95),
            "read_p99_ms": percentile(latencies, 0.99),
            "read_rps": args.reads / read_seconds,
            "intake_seconds": intake_seconds,
            "processing_seconds": processing_seconds,
            "processing_docs_per_minute": processed / processing_seconds * 60,
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "cpu_count": os.cpu_count(),
            },
            "raw_read_latencies_ms": [round(v, 4) for v in latencies],
            "limitations": [
                "Single host; no network/TLS, external OCR, model latency or object storage.",
                "Concurrency is 8 clients by default, not 1000 users. No PostgreSQL/cloud throughput claim.",
                "SQLite transaction serialization favors correctness; PostgreSQL scalability requires separate measurements.",
            ],
        }
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {k: v for k, v in report.items() if k != "raw_read_latencies_ms"},
                indent=2,
            )
        )
        store.engine.dispose()


if __name__ == "__main__":
    main()
