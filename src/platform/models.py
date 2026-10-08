from sqlalchemy import (
    Column,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    CheckConstraint,
)

metadata = MetaData()
members = Table(
    "members",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False),
    Column("name", String, nullable=False),
    Column("role", String, nullable=False),
    Column("token_hash", String, unique=True, nullable=False),
    CheckConstraint("role IN ('auditor','reviewer','owner','vendor')"),
)
requests = Table(
    "requests",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False),
    Column("title", String, nullable=False),
    Column("control_id", String, nullable=False),
    Column("owner_id", String, nullable=False),
    Column("vendor_id", String),
    Column("period", String, nullable=False),
    Column("status", String, nullable=False, default="awaiting_evidence"),
    Column("version", Integer, nullable=False, default=0),
    Column("canonical", Text, nullable=False, default="{}"),
    Column("updated_at", String, nullable=False),
    UniqueConstraint("tenant_id", "id"),
    CheckConstraint(
        "status IN ('awaiting_evidence','processing','ready','needs_changes','approved','rejected')"
    ),
)
documents = Table(
    "documents",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False),
    Column("request_id", String, nullable=False),
    Column("filename", String, nullable=False),
    Column("media_type", String, nullable=False),
    Column("content", Text, nullable=False),
    Column("digest", String, nullable=False),
    Column("payload_hash", String, nullable=False),
    Column("idempotency_key", String, nullable=False),
    Column("submitted_by", String, nullable=False),
    Column("extraction", Text),
    Column("created_at", String, nullable=False),
    UniqueConstraint("tenant_id", "idempotency_key"),
    UniqueConstraint("tenant_id", "id"),
    ForeignKeyConstraint(
        ["tenant_id", "request_id"], ["requests.tenant_id", "requests.id"]
    ),
)
jobs = Table(
    "jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False),
    Column("request_id", String, nullable=False),
    Column("document_id", String, nullable=False),
    Column("status", String, nullable=False, default="queued"),
    Column("attempts", Integer, nullable=False, default=0),
    Column("lease_token", String),
    Column("lease_until", String),
    Column("available_at", String, nullable=False),
    Column("created_at", String, nullable=False),
    Column("finished_at", String),
    Column("error", String),
    ForeignKeyConstraint(
        ["tenant_id", "document_id"], ["documents.tenant_id", "documents.id"]
    ),
    CheckConstraint("status IN ('queued','running','succeeded','dead_letter')"),
)
events = Table(
    "audit_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tenant_id", String, nullable=False),
    Column("request_id", String, nullable=False),
    Column("actor", String, nullable=False),
    Column("event_type", String, nullable=False),
    Column("payload", Text, nullable=False),
    Column("created_at", String, nullable=False),
    Column("previous_hash", String, nullable=False),
    Column("event_hash", String, nullable=False),
    ForeignKeyConstraint(
        ["tenant_id", "request_id"], ["requests.tenant_id", "requests.id"]
    ),
)
Index("ix_request_tenant", requests.c.tenant_id, requests.c.updated_at)
Index("ix_job_claim", jobs.c.tenant_id, jobs.c.status, jobs.c.available_at)
Index("ix_event_lineage", events.c.tenant_id, events.c.request_id, events.c.id)

invitations = Table(
    "invitations",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False),
    Column("request_id", String, nullable=False),
    Column("token_hash", String, unique=True, nullable=False),
    Column("created_by", String, nullable=False),
    Column("created_at", String, nullable=False),
    Column("expires_at", String, nullable=False),
    Column("accepted_at", String),
    Column("revoked_at", String),
    UniqueConstraint("tenant_id", "request_id", "id"),
    ForeignKeyConstraint(
        ["tenant_id", "request_id"], ["requests.tenant_id", "requests.id"]
    ),
)
external_sessions = Table(
    "external_sessions",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False),
    Column("request_id", String, nullable=False),
    Column("invitation_id", String, nullable=False),
    Column("name", String, nullable=False),
    Column("token_hash", String, unique=True, nullable=False),
    Column("created_at", String, nullable=False),
    UniqueConstraint("invitation_id"),
    ForeignKeyConstraint(
        ["tenant_id", "request_id", "invitation_id"],
        ["invitations.tenant_id", "invitations.request_id", "invitations.id"],
    ),
)

revisions = Table(
    "document_revisions",
    metadata,
    Column("tenant_id", String, nullable=False),
    Column("request_id", String, nullable=False),
    Column("previous_id", String, primary_key=True),
    Column("replacement_id", String, unique=True, nullable=False),
    Column("created_at", String, nullable=False),
    ForeignKeyConstraint(
        ["tenant_id", "request_id"], ["requests.tenant_id", "requests.id"]
    ),
    ForeignKeyConstraint(
        ["tenant_id", "request_id", "previous_id"],
        ["documents.tenant_id", "documents.request_id", "documents.id"],
    ),
    ForeignKeyConstraint(
        ["tenant_id", "request_id", "replacement_id"],
        ["documents.tenant_id", "documents.request_id", "documents.id"],
    ),
    CheckConstraint("previous_id != replacement_id"),
)

accept_limits = Table(
    "invitation_accept_limits",
    metadata,
    Column("client_hash", String, primary_key=True),
    Column("window", Integer, nullable=False),
    Column("attempts", Integer, nullable=False),
)

Index(
    "uq_document_request_identity",
    documents.c.tenant_id,
    documents.c.request_id,
    documents.c.id,
    unique=True,
)
