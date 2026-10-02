from __future__ import annotations

import json
import os
from typing import Protocol

import pandas as pd

try:
    from .schemas import AgentDecision, RetrievedChunk
except ImportError:
    from schemas import AgentDecision, RetrievedChunk


VALID_STATUSES = {"supported", "partial", "gap", "missing"}


class AuditReasoner(Protocol):
    def reason(
        self,
        control: pd.Series,
        deterministic,
        retrieved: list[RetrievedChunk],
    ) -> AgentDecision:
        ...


class HeuristicAuditReasoner:
    """Offline reasoner used for tests and reproducible demos.

    It converts the deterministic baseline into an agent-shaped decision while
    restricting every citation to retrieved context.
    """

    provider = "heuristic-guardrail"

    def reason(
        self,
        control: pd.Series,
        deterministic,
        retrieved: list[RetrievedChunk],
    ) -> AgentDecision:
        evidence_ids = (
            [deterministic.best_evidence_id]
            if deterministic.best_evidence_id
            else []
        )
        citations = [
            chunk.source_id
            for chunk in retrieved
            if chunk.source_id == f"control:{control['control_id']}"
            or (
                deterministic.best_evidence_id
                and chunk.source_id
                == f"evidence:{deterministic.best_evidence_id}"
            )
            or chunk.document_type == "knowledge"
        ][:4]

        if deterministic.status == "missing":
            confidence = 0.99
            missing = [str(control["required_evidence_type"])]
        elif deterministic.exception_terms:
            confidence = 0.86
            missing = []
        elif deterministic.status == "partial":
            confidence = 0.80
            missing = ["additional or in-period supporting evidence"]
        else:
            confidence = min(0.98, 0.75 + deterministic.score / 400)
            missing = []

        exception = ""
        if deterministic.exception_terms:
            exception = (
                "Evidence contains exception indicators: "
                + ", ".join(deterministic.exception_terms)
            )

        return AgentDecision(
            control_id=str(control["control_id"]),
            status=deterministic.status,
            confidence=round(confidence, 3),
            requirement_summary=str(control["requirement"]),
            evidence_ids=evidence_ids,
            citations=citations,
            exception=exception,
            missing_evidence=missing,
            reasoning=(
                "Deterministic validation was used as a guardrail for evidence "
                "type, period, keyword coverage, and explicit exception terms. "
                f"Baseline reasoning: {deterministic.reasoning}"
            ),
            provider=self.provider,
        )


class OpenAIAuditReasoner:
    def __init__(self, model: str = "gpt-5-mini"):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "Install the optional openai package to use provider=openai."
            ) from exc

        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is required when provider=openai."
            )
        self.client = OpenAI()
        self.model = model
        self.provider = f"openai:{model}"

    def reason(
        self,
        control: pd.Series,
        deterministic,
        retrieved: list[RetrievedChunk],
    ) -> AgentDecision:
        allowed_citations = [chunk.source_id for chunk in retrieved]
        context = "\n\n".join(
            f"[{chunk.source_id}]\n{chunk.text}"
            for chunk in retrieved
        )

        prompt = f"""
You are an audit-evidence analysis agent. You assist a human reviewer; you do
not issue an audit opinion.

Control ID: {control['control_id']}
Title: {control['title']}
Requirement: {control['requirement']}
Required evidence type: {control['required_evidence_type']}
Target period: {control['target_period']}

Deterministic guardrail:
- status: {deterministic.status}
- score: {deterministic.score}
- reasoning: {deterministic.reasoning}
- exception terms: {deterministic.exception_terms}

Retrieved context:
{context}

Return one JSON object with exactly these keys:
status, confidence, requirement_summary, evidence_ids, citations, exception,
missing_evidence, reasoning.

Rules:
- status must be supported, partial, gap, or missing.
- confidence must be between 0 and 1.
- citations may ONLY use these source IDs: {allowed_citations}
- do not invent evidence IDs, dates, approvals, owners, or test results.
- identify missing evidence explicitly.
- if evidence contains an exception, surface it even if the control otherwise
  appears supported.
- reasoning must be concise and reviewable by a human auditor.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Return strict JSON only. Ground every factual conclusion "
                        "in the provided retrieved context."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        status = str(payload.get("status", "gap")).lower()
        if status not in VALID_STATUSES:
            status = "gap"

        return AgentDecision(
            control_id=str(control["control_id"]),
            status=status,
            confidence=max(
                0.0, min(1.0, float(payload.get("confidence", 0.0)))
            ),
            requirement_summary=str(
                payload.get("requirement_summary", control["requirement"])
            ),
            evidence_ids=[
                str(value) for value in payload.get("evidence_ids", [])
            ],
            citations=[
                str(value) for value in payload.get("citations", [])
            ],
            exception=str(payload.get("exception", "")),
            missing_evidence=[
                str(value)
                for value in payload.get("missing_evidence", [])
            ],
            reasoning=str(payload.get("reasoning", "")),
            provider=self.provider,
        )


def make_reasoner(
    provider: str = "heuristic",
    model: str = "gpt-5-mini",
) -> AuditReasoner:
    if provider == "heuristic":
        return HeuristicAuditReasoner()
    if provider == "openai":
        return OpenAIAuditReasoner(model=model)
    raise ValueError(f"Unsupported provider: {provider}")
