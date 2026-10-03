from sqlalchemy import (
    Column,
    Table,
    String,
    Text,
    Integer,
    ForeignKeyConstraint,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from src.platform.models import metadata

runs = Table(
    "agent_runs",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False),
    Column("request_id", String, nullable=False),
    Column("snapshot_version", Integer, nullable=False),
    Column("provider", String, nullable=False),
    Column("snapshot", Text, nullable=False),
    Column("status", String, nullable=False),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
    Column("assessment", Text, nullable=False, default="{}"),
    Column("grounding", Text, nullable=False, default="{}"),
    Column("report", Text),
    Column("start_key", String, nullable=False),
    Column("start_hash", String, nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
    Column("lease_token", String),
    Column("lease_until", String),
    Column("available_at", String, nullable=False),
    Column("error", String),
    UniqueConstraint("tenant_id", "id"),
    UniqueConstraint("tenant_id", "start_key"),
    UniqueConstraint("tenant_id", "request_id", "snapshot_version", "provider"),
    ForeignKeyConstraint(
        ["tenant_id", "request_id"], ["requests.tenant_id", "requests.id"]
    ),
    CheckConstraint(
        "status IN ('queued','running','waiting_review','completed','failed','superseded')"
    ),
)
commands = Table(
    "agent_review_commands",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False),
    Column("request_id", String, nullable=False),
    Column("run_id", String, nullable=False),
    Column("reviewer", String, nullable=False),
    Column("decision", String, nullable=False),
    Column("feedback", Text, nullable=False),
    Column("snapshot_version", Integer, nullable=False),
    Column("result_version", Integer, nullable=False),
    Column("key", String, nullable=False),
    Column("payload_hash", String, nullable=False),
    Column("created_at", String, nullable=False),
    UniqueConstraint("tenant_id", "run_id"),
    UniqueConstraint("tenant_id", "key"),
    ForeignKeyConstraint(
        ["tenant_id", "run_id"], ["agent_runs.tenant_id", "agent_runs.id"]
    ),
)
run_events = Table(
    "agent_run_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tenant_id", String, nullable=False),
    Column("run_id", String, nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("node", String, nullable=False),
    Column("outcome", String, nullable=False),
    Column("duration_ms", Integer, nullable=False),
    Column("output_digest", String, nullable=False),
    Column("created_at", String, nullable=False),
    UniqueConstraint("tenant_id", "run_id", "sequence"),
    ForeignKeyConstraint(
        ["tenant_id", "run_id"], ["agent_runs.tenant_id", "agent_runs.id"]
    ),
)
Index("ix_agent_claim", runs.c.tenant_id, runs.c.status, runs.c.available_at)
