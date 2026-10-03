from datetime import datetime, timezone
import hashlib
import json
import uuid

from sqlalchemy import insert, or_, select, update, text

from .auth import Principal, token_hash
from .models import documents, events, jobs, members, requests


class DomainError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message
        super().__init__(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def packed(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def append_event(conn, principal, request_id, event_type, payload):
    previous = (
        conn.execute(
            select(events.c.event_hash)
            .where(
                events.c.tenant_id == principal.tenant_id,
                events.c.request_id == request_id,
            )
            .order_by(events.c.id.desc())
            .limit(1)
        ).scalar()
        or "0" * 64
    )
    record = dict(
        tenant_id=principal.tenant_id,
        request_id=request_id,
        actor=principal.id,
        event_type=event_type,
        payload=packed(payload),
        created_at=now(),
        previous_hash=previous,
    )
    conn.execute(insert(events).values(**record, event_hash=digest(packed(record))))


class EvidenceService:
    def __init__(self, store):
        self.store = store

    def authenticate(self, token):
        with self.store.transaction() as conn:
            row = (
                conn.execute(
                    select(members).where(members.c.token_hash == token_hash(token))
                )
                .mappings()
                .first()
            )
            if not row:
                raise DomainError(401, "Invalid API token")
            return Principal(row["id"], row["tenant_id"], row["role"], row["name"])

    def scope(self, principal):
        clause = requests.c.tenant_id == principal.tenant_id
        if principal.role in {"owner", "vendor"}:
            clause = clause & or_(
                requests.c.owner_id == principal.id,
                requests.c.vendor_id == principal.id,
            )
        return clause

    def _request(self, conn, principal, request_id, lock=False):
        query = select(requests).where(
            self.scope(principal), requests.c.id == request_id
        )
        if lock:
            query = query.with_for_update()
        row = conn.execute(query).mappings().first()
        if not row:
            raise DomainError(404, "Request not found")
        return dict(row)

    def list_requests(self, principal):
        with self.store.transaction(principal.tenant_id) as conn:
            rows = conn.execute(
                select(requests).where(self.scope(principal)).order_by(requests.c.id)
            ).mappings()
            return [{**r, "canonical": json.loads(r["canonical"])} for r in rows]

    def detail(self, principal, request_id):
        with self.store.transaction(principal.tenant_id) as conn:
            record = self._request(conn, principal, request_id)
            record["canonical"] = json.loads(record["canonical"])
            for name, table in [
                ("documents", documents),
                ("jobs", jobs),
                ("events", events),
            ]:
                cols = [
                    c
                    for c in table.c
                    if c.name
                    not in {"content", "payload_hash", "idempotency_key", "lease_token"}
                ]
                query = (
                    select(*cols)
                    .where(
                        table.c.tenant_id == principal.tenant_id,
                        table.c.request_id == request_id,
                    )
                    .order_by(table.c.id)
                )
                record[name] = [dict(r) for r in conn.execute(query).mappings()]
            for doc in record["documents"]:
                doc["extraction"] = (
                    json.loads(doc["extraction"]) if doc["extraction"] else None
                )
            for event in record["events"]:
                event["payload"] = json.loads(event["payload"])
            return record

    def submit(self, principal, request_id, key, document):
        content = document.get("content", "")
        filename = document.get("filename", "")
        media_type = document.get("media_type", "")
        if not isinstance(content, str) or not content.strip() or len(content) > 200000:
            raise DomainError(422, "Document must contain 1–200000 characters")
        if media_type not in {"text/plain", "text/csv", "application/json"}:
            raise DomainError(
                422,
                "Submit normalized text, CSV or JSON; binary extraction is a separate intake step",
            )
        if not filename or len(filename) > 120 or "/" in filename or "\\" in filename:
            raise DomainError(422, "Invalid filename")
        if not key or len(key) > 120:
            raise DomainError(422, "Idempotency-Key must contain 1–120 characters")
        fingerprint = digest(packed({"request_id": request_id, **document}))
        with self.store.transaction(principal.tenant_id) as conn:
            if self.store.engine.dialect.name == "postgresql":
                # Key scope is tenant-wide, so locking only one request is insufficient.
                conn.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
                    {"scope": packed([principal.tenant_id, key])},
                )
            record = self._request(conn, principal, request_id, lock=True)
            old = (
                conn.execute(
                    select(documents).where(
                        documents.c.tenant_id == principal.tenant_id,
                        documents.c.idempotency_key == key,
                    )
                )
                .mappings()
                .first()
            )
            if old:
                if old["payload_hash"] != fingerprint:
                    raise DomainError(
                        409, "Idempotency key was already used for a different payload"
                    )
                job_id = conn.execute(
                    select(jobs.c.id).where(
                        jobs.c.tenant_id == principal.tenant_id,
                        jobs.c.document_id == old["id"],
                    )
                ).scalar_one()
                return {"document_id": old["id"], "job_id": job_id, "replayed": True}
            if record["status"] == "approved":
                raise DomainError(
                    409, "Approved record is immutable; open a new evidence request"
                )
            if principal.role == "reviewer":
                raise DomainError(403, "Reviewers cannot submit evidence")
            did, jid, timestamp = uuid.uuid4().hex, uuid.uuid4().hex, now()
            conn.execute(
                insert(documents).values(
                    id=did,
                    tenant_id=principal.tenant_id,
                    request_id=request_id,
                    filename=filename,
                    media_type=media_type,
                    content=content,
                    digest=digest(content),
                    payload_hash=fingerprint,
                    idempotency_key=key,
                    submitted_by=principal.id,
                    created_at=timestamp,
                )
            )
            conn.execute(
                insert(jobs).values(
                    id=jid,
                    tenant_id=principal.tenant_id,
                    request_id=request_id,
                    document_id=did,
                    status="queued",
                    attempts=0,
                    available_at=timestamp,
                    created_at=timestamp,
                )
            )
            conn.execute(
                update(requests)
                .where(
                    requests.c.id == request_id,
                    requests.c.tenant_id == principal.tenant_id,
                )
                .values(
                    status="processing",
                    version=record["version"] + 1,
                    updated_at=timestamp,
                )
            )
            append_event(
                conn,
                principal,
                request_id,
                "document.submitted",
                {"document_id": did, "job_id": jid, "digest": digest(content)},
            )
            return {"document_id": did, "job_id": jid, "replayed": False}

    def review(self, principal, request_id, version, decision, feedback):
        with self.store.transaction(principal.tenant_id) as conn:
            self.review_in_transaction(
                conn, principal, request_id, version, decision, feedback
            )
        return self.detail(principal, request_id)

    def review_in_transaction(
        self, conn, principal, request_id, version, decision, feedback, provenance=None
    ):
        if principal.role != "reviewer":
            raise DomainError(403, "Reviewer membership required")
        if (
            decision not in {"approve", "reject", "needs_changes"}
            or len(feedback) > 1000
        ):
            raise DomainError(422, "Invalid review")
        record = self._request(conn, principal, request_id, lock=True)
        if record["version"] != version or record["status"] == "approved":
            raise DomainError(409, "Record changed; reload before reviewing")
        if record["status"] in {"awaiting_evidence", "processing"}:
            raise DomainError(409, "Processing must finish before review")
        authors = set(
            conn.execute(
                select(documents.c.submitted_by).where(
                    documents.c.tenant_id == principal.tenant_id,
                    documents.c.request_id == request_id,
                )
            ).scalars()
        )
        if principal.id in authors or principal.id == record["owner_id"]:
            raise DomainError(403, "Evidence submitter cannot approve their own record")
        canonical = json.loads(record["canonical"])
        if decision == "approve" and (
            canonical.get("exceptions") or not canonical.get("complete")
        ):
            raise DomainError(409, "Resolve evidence exceptions before approval")
        status = {
            "approve": "approved",
            "reject": "rejected",
            "needs_changes": "needs_changes",
        }[decision]
        conn.execute(
            update(requests)
            .where(
                requests.c.id == request_id,
                requests.c.tenant_id == principal.tenant_id,
            )
            .values(status=status, version=version + 1, updated_at=now())
        )
        append_event(
            conn,
            principal,
            request_id,
            "review." + decision,
            {"version": version, "feedback": feedback, **(provenance or {})},
        )
        return {"version": version + 1, "status": status}

    def verify_history(self, principal, request_id):
        record = self.detail(principal, request_id)
        previous = "0" * 64
        for event in record["events"]:
            body = {
                k: event[k]
                for k in [
                    "tenant_id",
                    "request_id",
                    "actor",
                    "event_type",
                    "created_at",
                    "previous_hash",
                ]
            }
            body["payload"] = packed(event["payload"])
            if (
                event["previous_hash"] != previous
                or digest(packed(body)) != event["event_hash"]
            ):
                return {"valid": False, "events": len(record["events"])}
            previous = event["event_hash"]
        return {"valid": True, "events": len(record["events"]), "head": previous}
