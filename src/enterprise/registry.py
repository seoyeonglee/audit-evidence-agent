import json
import uuid
from sqlalchemy import insert, select, text
from src.platform.service import EvidenceService, DomainError, packed, digest, now
from .models import runs, commands, run_events
from .snapshot import snapshot_request


def decode(row):
    result = dict(row)
    for key in ["snapshot", "assessment", "grounding", "report"]:
        if key in result:
            result[key] = json.loads(result[key]) if result[key] else None
    for key in ["lease_token", "start_hash", "start_key"]:
        result.pop(key, None)
    return result


class RunRegistry:
    def __init__(self, store):
        self.store = store

    def scoped(self, conn, principal, run_id, lock=False):
        q = select(runs).where(
            runs.c.id == run_id, runs.c.tenant_id == principal.tenant_id
        )
        if lock:
            q = q.with_for_update()
        row = conn.execute(q).mappings().first()
        if not row:
            raise DomainError(404, "Agent run not found")
        EvidenceService(self.store)._request(conn, principal, row["request_id"])
        return dict(row)

    def start(self, principal, request_id, expected_version, provider, key):
        if principal.role not in {"reviewer", "auditor"}:
            raise DomainError(403, "Reviewer or auditor required to start a run")
        if provider != "heuristic" or not key or len(key) > 120:
            raise DomainError(422, "Only bounded offline heuristic runs are enabled")
        fingerprint = digest(packed([request_id, expected_version, provider]))
        with self.store.transaction(principal.tenant_id) as conn:
            if self.store.engine.dialect.name == "postgresql":
                conn.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:scope,0))"),
                    {"scope": packed([principal.tenant_id, key])},
                )
            EvidenceService(self.store)._request(conn, principal, request_id, lock=True)
            replay = (
                conn.execute(
                    select(runs).where(
                        runs.c.tenant_id == principal.tenant_id, runs.c.start_key == key
                    )
                )
                .mappings()
                .first()
            )
            if replay:
                if replay["start_hash"] != fingerprint:
                    raise DomainError(409, "Start key already used for another payload")
                return decode(replay)
            snapshot = snapshot_request(conn, principal, request_id, expected_version)
            existing = (
                conn.execute(
                    select(runs).where(
                        runs.c.tenant_id == principal.tenant_id,
                        runs.c.request_id == request_id,
                        runs.c.snapshot_version == expected_version,
                        runs.c.provider == provider,
                    )
                )
                .mappings()
                .first()
            )
            if existing:
                return decode(existing)
            record = dict(
                id=uuid.uuid4().hex,
                tenant_id=principal.tenant_id,
                request_id=request_id,
                snapshot_version=expected_version,
                provider=provider,
                snapshot=packed(snapshot),
                status="queued",
                created_at=now(),
                updated_at=now(),
                available_at=now(),
                start_key=key,
                start_hash=fingerprint,
                assessment="{}",
                grounding="{}",
                attempts=0,
            )
            conn.execute(insert(runs).values(**record))
            return decode(record)

    def detail(self, principal, run_id):
        with self.store.transaction(principal.tenant_id) as conn:
            row = self.scoped(conn, principal, run_id)
            result = decode(row)
            result["events"] = [
                dict(r)
                for r in conn.execute(
                    select(run_events)
                    .where(
                        run_events.c.tenant_id == principal.tenant_id,
                        run_events.c.run_id == run_id,
                    )
                    .order_by(run_events.c.sequence)
                ).mappings()
            ]
            command = (
                conn.execute(
                    select(commands).where(
                        commands.c.tenant_id == principal.tenant_id,
                        commands.c.run_id == run_id,
                    )
                )
                .mappings()
                .first()
            )
            result["review"] = dict(command) if command else None
            if result["review"]:
                result["review"].pop("payload_hash", None)
                result["review"].pop("key", None)
            current = EvidenceService(self.store)._request(
                conn, principal, row["request_id"]
            )
            result["current_version"] = current["version"]
            result["stale"] = (
                not command and current["version"] != row["snapshot_version"]
            )
            return result

    def list_for_request(self, principal, request_id):
        with self.store.transaction(principal.tenant_id) as conn:
            EvidenceService(self.store)._request(conn, principal, request_id)
            return [
                decode(r)
                for r in conn.execute(
                    select(runs)
                    .where(
                        runs.c.tenant_id == principal.tenant_id,
                        runs.c.request_id == request_id,
                    )
                    .order_by(runs.c.created_at.desc())
                ).mappings()
            ]
