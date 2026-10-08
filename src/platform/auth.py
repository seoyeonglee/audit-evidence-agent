from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class Principal:
    id: str
    tenant_id: str
    role: str
    name: str
    request_id: str | None = None
    session_id: str | None = None


def token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()
