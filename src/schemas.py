from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RetrievedChunk:
    source_id: str
    document_type: str
    text: str
    score: float


@dataclass
class AgentDecision:
    control_id: str
    status: str
    confidence: float
    requirement_summary: str
    evidence_ids: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    exception: str = ""
    missing_evidence: list[str] = field(default_factory=list)
    reasoning: str = ""
    provider: str = "heuristic-guardrail"
