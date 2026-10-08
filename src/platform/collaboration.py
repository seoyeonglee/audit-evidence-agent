"""One-request capability invitations; plaintext tokens never enter stored history."""

import base64
from datetime import datetime, timedelta, timezone
import secrets
import uuid

from sqlalchemy import insert, select, update

from .auth import Principal, token_hash
from .models import external_sessions, invitations
from .service import DomainError, EvidenceService, append_event


def capability(prefix, tenant):
    locator = base64.urlsafe_b64encode(tenant.encode()).decode().rstrip("=")
    return f"{prefix}.{locator}.{secrets.token_urlsafe(32)}"


def locator(token, prefix):
    try:
        parts = token.split(".")
        if (
            len(parts) != 3
            or parts[0] != prefix
            or len(token) > 512
            or len(parts[2]) != 43
        ):
            raise ValueError()
        tenant = base64.b64decode(
            parts[1] + "=" * (-len(parts[1]) % 4), altchars=b"-_", validate=True
        ).decode()
        if not tenant or len(tenant) > 120:
            raise ValueError()
        return tenant
    except (ValueError, UnicodeError):
        raise DomainError(401, "Invalid or unavailable capability") from None


def valid_invitation(row, timestamp):
    return row and not row["revoked_at"] and row["expires_at"] > timestamp


def check_external(conn, principal, timestamp):
    if not principal.session_id:
        return
    row = (
        conn.execute(
            select(invitations)
            .join(
                external_sessions,
                (external_sessions.c.invitation_id == invitations.c.id)
                & (external_sessions.c.tenant_id == invitations.c.tenant_id),
            )
            .where(
                external_sessions.c.id == principal.session_id,
                external_sessions.c.tenant_id == principal.tenant_id,
                external_sessions.c.request_id == principal.request_id,
            )
            .with_for_update(of=invitations)
        )
        .mappings()
        .first()
    )
    if not valid_invitation(row, timestamp):
        raise DomainError(401, "External session expired or revoked")


class CollaborationService:
    def __init__(self, store, clock=None):
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.evidence = EvidenceService(store)

    def create_invitation(self, principal, request_id, ttl_hours=24):
        if principal.role != "reviewer":
            raise DomainError(403, "Reviewer membership required")
        if (
            not isinstance(ttl_hours, int)
            or isinstance(ttl_hours, bool)
            or not 1 <= ttl_hours <= 168
        ):
            raise DomainError(422, "Lifetime must be 1–168 hours")
        token = capability("invite", principal.tenant_id)
        timestamp = self.clock()
        row = dict(
            id=uuid.uuid4().hex,
            tenant_id=principal.tenant_id,
            request_id=request_id,
            token_hash=token_hash(token),
            created_by=principal.id,
            created_at=timestamp.isoformat(),
            expires_at=(timestamp + timedelta(hours=ttl_hours)).isoformat(),
        )
        with self.store.transaction(principal.tenant_id) as conn:
            self.evidence._request(conn, principal, request_id, lock=True)
            conn.execute(insert(invitations).values(**row))
            append_event(
                conn,
                principal,
                request_id,
                "invitation.created",
                {"invitation_id": row["id"], "expires_at": row["expires_at"]},
            )
        return {k: v for k, v in row.items() if k != "token_hash"} | {"token": token}

    def list_invitations(self, principal, request_id):
        if principal.role != "reviewer":
            raise DomainError(403, "Reviewer membership required")
        with self.store.transaction(principal.tenant_id) as conn:
            self.evidence._request(conn, principal, request_id)
            cols = [c for c in invitations.c if c.name != "token_hash"]
            return [
                dict(r)
                for r in conn.execute(
                    select(*cols).where(
                        invitations.c.tenant_id == principal.tenant_id,
                        invitations.c.request_id == request_id,
                    )
                ).mappings()
            ]

    def accept_invitation(self, token, name):
        tenant = locator(token, "invite")
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise DomainError(422, "Display name must contain 1–120 characters")
        timestamp = self.clock().isoformat()
        with self.store.transaction(tenant) as conn:
            row = (
                conn.execute(
                    select(invitations)
                    .where(
                        invitations.c.tenant_id == tenant,
                        invitations.c.token_hash == token_hash(token),
                    )
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if not valid_invitation(row, timestamp) or row["accepted_at"]:
                raise DomainError(401, "Invalid or unavailable invitation")
            session_token = capability("external", tenant)
            sid = uuid.uuid4().hex
            conn.execute(
                update(invitations)
                .where(invitations.c.id == row["id"], invitations.c.tenant_id == tenant)
                .values(accepted_at=timestamp)
            )
            conn.execute(
                insert(external_sessions).values(
                    id=sid,
                    tenant_id=tenant,
                    request_id=row["request_id"],
                    invitation_id=row["id"],
                    name=name.strip(),
                    token_hash=token_hash(session_token),
                    created_at=timestamp,
                )
            )
            principal = Principal(
                sid, tenant, "vendor", name.strip(), row["request_id"], sid
            )
            # Serialize the append-only chain with other request events.
            self.evidence._request(conn, principal, row["request_id"], lock=True)
            append_event(
                conn,
                principal,
                row["request_id"],
                "invitation.accepted",
                {"invitation_id": row["id"], "session_id": sid},
            )
        return {
            "token": session_token,
            "name": name.strip(),
            "role": "vendor",
            "tenant_id": tenant,
            "request_id": row["request_id"],
            "external": True,
            "expires_at": row["expires_at"],
        }

    def revoke_invitation(self, principal, request_id, invitation_id):
        if principal.role != "reviewer":
            raise DomainError(403, "Reviewer membership required")
        with self.store.transaction(principal.tenant_id) as conn:
            # Same invitation -> request order as accept/external operations.
            row = (
                conn.execute(
                    select(invitations)
                    .where(
                        invitations.c.id == invitation_id,
                        invitations.c.tenant_id == principal.tenant_id,
                        invitations.c.request_id == request_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if not row:
                raise DomainError(404, "Invitation not found")
            self.evidence._request(conn, principal, request_id, lock=True)
            if not row["revoked_at"]:
                conn.execute(
                    update(invitations)
                    .where(
                        invitations.c.id == invitation_id,
                        invitations.c.tenant_id == principal.tenant_id,
                    )
                    .values(revoked_at=self.clock().isoformat())
                )
                append_event(
                    conn,
                    principal,
                    request_id,
                    "invitation.revoked",
                    {"invitation_id": invitation_id},
                )
        return {"revoked": True}

    def authenticate(self, token):
        tenant = locator(token, "external")
        with self.store.transaction(tenant) as conn:
            row = (
                conn.execute(
                    select(external_sessions).where(
                        external_sessions.c.tenant_id == tenant,
                        external_sessions.c.token_hash == token_hash(token),
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                raise DomainError(401, "Invalid external session")
            user = Principal(
                row["id"], tenant, "vendor", row["name"], row["request_id"], row["id"]
            )
            check_external(conn, user, self.clock().isoformat())
            return user

    def limit_acceptance(self, peer):
        """Persistent per-transport-peer limit; never trust caller forwarding headers."""
        from sqlalchemy import text
        from .models import accept_limits

        key = token_hash(peer)
        window = int(self.clock().timestamp()) // 60
        blocked = False
        with self.store.transaction() as conn:
            if self.store.engine.dialect.name == "postgresql":
                conn.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                    {"key": key},
                )
            row = (
                conn.execute(
                    select(accept_limits)
                    .where(accept_limits.c.client_hash == key)
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if not row:
                conn.execute(
                    insert(accept_limits).values(
                        client_hash=key, window=window, attempts=1
                    )
                )
            elif row["window"] != window:
                conn.execute(
                    update(accept_limits)
                    .where(accept_limits.c.client_hash == key)
                    .values(window=window, attempts=1)
                )
            elif row["attempts"] >= 10:
                blocked = True
            else:
                conn.execute(
                    update(accept_limits)
                    .where(accept_limits.c.client_hash == key)
                    .values(attempts=row["attempts"] + 1)
                )
        if blocked:
            raise DomainError(
                429, "Too many invitation attempts; try again next minute"
            )
