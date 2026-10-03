import json
import uuid
from sqlalchemy import select, insert, text
from src.platform.service import EvidenceService, DomainError, packed, digest, now
from .registry import RunRegistry
from .models import commands


def review_run(store, principal, run_id, expected_version, decision, feedback, key):
    if (
        not key
        or len(key) > 120
        or len(feedback) > 1000
        or decision not in {"approve", "reject", "needs_changes"}
    ):
        raise DomainError(422, "Invalid bounded review input")
    fingerprint = digest(
        packed([run_id, expected_version, decision, feedback, principal.id])
    )
    with store.transaction(principal.tenant_id) as conn:
        if store.engine.dialect.name == "postgresql":
            conn.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:scope,0))"),
                {"scope": packed([principal.tenant_id, key])},
            )
        run = RunRegistry(store).scoped(conn, principal, run_id, lock=True)
        if principal.role != "reviewer":
            raise DomainError(403, "Independent reviewer required")
        old = (
            conn.execute(
                select(commands).where(
                    commands.c.tenant_id == principal.tenant_id, commands.c.key == key
                )
            )
            .mappings()
            .first()
        )
        if old:
            if old["payload_hash"] != fingerprint:
                raise DomainError(
                    409, "Review key already used for a different payload"
                )
            return dict(old)
        if (
            run["status"] != "waiting_review"
            or run["snapshot_version"] != expected_version
        ):
            raise DomainError(409, "Run is not awaiting this review version")
        if conn.execute(
            select(commands.c.id).where(
                commands.c.tenant_id == principal.tenant_id, commands.c.run_id == run_id
            )
        ).first():
            raise DomainError(409, "Run already reviewed")
        if decision == "approve" and not json.loads(run["grounding"]).get("valid"):
            raise DomainError(409, "Grounding validation blocks approval")
        cid = uuid.uuid4().hex
        reviewed = EvidenceService(store).review_in_transaction(
            conn,
            principal,
            run["request_id"],
            expected_version,
            decision,
            feedback,
            {"agent_run_id": run_id, "command_id": cid},
        )
        row = dict(
            id=cid,
            tenant_id=principal.tenant_id,
            request_id=run["request_id"],
            run_id=run_id,
            reviewer=principal.id,
            decision=decision,
            feedback=feedback,
            snapshot_version=expected_version,
            result_version=reviewed["version"],
            key=key,
            payload_hash=fingerprint,
            created_at=now(),
        )
        conn.execute(insert(commands).values(**row))
        return row
