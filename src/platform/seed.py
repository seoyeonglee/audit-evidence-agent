import secrets
from sqlalchemy import insert, select, update

from .auth import token_hash
from .models import members, requests
from .service import now

PERSONAS = {
    'reviewer': ('demo-acme','reviewer','Maya Chen'),
    'auditor': ('demo-acme','auditor','Elliot Park'),
    'owner': ('demo-acme','owner','Alex Rivera'),
    'vendor': ('demo-acme','vendor','Jordan Vale'),
    'other-reviewer': ('demo-north','reviewer','Nora Kim'),
}


def seed_demo(store):
    """Synthetic bootstrap. Tokens are random; only their hashes are persisted."""
    tokens = {}
    for key, (tenant, role, name) in PERSONAS.items():
        token = secrets.token_urlsafe(32)
        tokens[key] = token
        with store.transaction(tenant) as conn:
            if conn.execute(select(members.c.id).where(members.c.id == key)).first():
                conn.execute(update(members).where(members.c.id == key).values(token_hash=token_hash(token)))
            else:
                conn.execute(insert(members).values(id=key, tenant_id=tenant, role=role, name=name, token_hash=token_hash(token)))
    rows = [
        ('REQ-ACCESS','demo-acme','Quarterly privileged access review','AC-01','owner',None),
        ('REQ-VENDOR','demo-acme','Vendor security attestation','VM-01','auditor','vendor'),
        ('REQ-BACKUP','demo-acme','Recovery drill evidence','BC-01','auditor',None),
        ('REQ-OTHER','demo-north','Restricted organization record','AC-01','other-reviewer',None),
    ]
    for rid, tenant, title, control, owner, vendor in rows:
        with store.transaction(tenant) as conn:
            if not conn.execute(select(requests.c.id).where(requests.c.id == rid)).first():
                conn.execute(insert(requests).values(id=rid, tenant_id=tenant, title=title,
                    control_id=control, owner_id=owner, vendor_id=vendor, period='2026-Q3',
                    status='awaiting_evidence', version=0, canonical='{}', updated_at=now()))
    return tokens
