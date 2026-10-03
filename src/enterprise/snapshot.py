import json
import csv
from pathlib import Path
from sqlalchemy import select
from src.platform.models import documents
from src.platform.service import EvidenceService, DomainError


def snapshot_request(conn, principal, request_id, expected_version):
    record = EvidenceService(None)._request(conn, principal, request_id, lock=True)
    if record["version"] != expected_version:
        raise DomainError(409, "Record version changed; reload before starting")
    if record["status"] in {"awaiting_evidence", "processing", "approved"}:
        raise DomainError(
            409, "Finish processing an unapproved request before starting"
        )
    docs = [
        dict(r)
        for r in conn.execute(
            select(documents)
            .where(
                documents.c.tenant_id == principal.tenant_id,
                documents.c.request_id == request_id,
            )
            .order_by(documents.c.id)
        ).mappings()
    ]
    if not docs or len(docs) > 20 or any(len(d["content"]) > 200000 for d in docs):
        raise DomainError(422, "Snapshot requires 1–20 bounded documents")
    control = next(
        (
            row
            for row in csv.DictReader(
                (Path(__file__).resolve().parents[2] / "data/controls.csv").open()
            )
            if row["control_id"] == record["control_id"]
        ),
        {},
    )
    guidance = (
        Path(__file__).resolve().parents[2] / "data/knowledge_base/control_guidance.md"
    ).read_text()
    return {
        "control_definition": control,
        "guidance": guidance,
        "request_id": request_id,
        "version": record["version"],
        "title": record["title"],
        "control_id": record["control_id"],
        "period": record["period"],
        "canonical": json.loads(record["canonical"]),
        "documents": [
            {
                "id": d["id"],
                "digest": d["digest"],
                "filename": d["filename"],
                "media_type": d["media_type"],
                "content": d["content"],
                "extraction": json.loads(d["extraction"]) if d["extraction"] else None,
            }
            for d in docs
        ],
    }
