from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd


EXCEPTION_TERMS = (
    "exception",
    "failed",
    "overdue",
    "not completed",
    "missing",
    "pending remediation",
)


@dataclass
class Assessment:
    control_id: str
    best_evidence_id: str
    evidence_type_match: bool
    period_match: bool
    keyword_coverage: float
    exception_terms: list[str]
    score: int
    status: str
    reasoning: str


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def keyword_list(raw: str) -> list[str]:
    return [
        normalize(part)
        for part in str(raw).split("|")
        if normalize(part)
    ]


def keyword_coverage(text: str, keywords: list[str]) -> tuple[float, list[str]]:
    if not keywords:
        return 1.0, []

    normalized = normalize(text)
    matched = [kw for kw in keywords if kw in normalized]
    return len(matched) / len(keywords), matched


def exception_hits(text: str) -> list[str]:
    normalized = normalize(text)
    return [term for term in EXCEPTION_TERMS if term in normalized]


def score_candidate(
    control: pd.Series,
    evidence_row: pd.Series,
    evidence_text: str,
) -> dict:
    required_type = normalize(control["required_evidence_type"])
    evidence_type = normalize(evidence_row["evidence_type"])
    type_match = required_type == evidence_type

    target_period = normalize(control["target_period"])
    evidence_period = normalize(evidence_row["period"])
    period_match = (not target_period) or target_period == evidence_period

    keywords = keyword_list(control["keywords"])
    coverage, matched_keywords = keyword_coverage(evidence_text, keywords)
    exceptions = exception_hits(evidence_text)

    score = 0
    if type_match:
        score += 45
    if period_match:
        score += 15
    score += round(coverage * 40)
    score -= min(30, 10 * len(exceptions))
    score = max(0, min(100, score))

    return {
        "evidence_id": str(evidence_row["evidence_id"]),
        "type_match": type_match,
        "period_match": period_match,
        "keyword_coverage": coverage,
        "matched_keywords": matched_keywords,
        "exception_terms": exceptions,
        "score": score,
    }


def status_for(score: int, evidence_id: str) -> str:
    if not evidence_id:
        return "missing"
    if score >= 80:
        return "supported"
    if score >= 50:
        return "partial"
    return "gap"


def assess_control(
    control: pd.Series,
    evidence_index: pd.DataFrame,
    evidence_texts: dict[str, str],
) -> Assessment:
    candidates = []

    for _, evidence_row in evidence_index.iterrows():
        evidence_id = str(evidence_row["evidence_id"])
        text = evidence_texts.get(evidence_id, "")
        candidate = score_candidate(control, evidence_row, text)
        candidates.append(candidate)

    if not candidates:
        return Assessment(
            control_id=str(control["control_id"]),
            best_evidence_id="",
            evidence_type_match=False,
            period_match=False,
            keyword_coverage=0.0,
            exception_terms=[],
            score=0,
            status="missing",
            reasoning="No evidence files were available for assessment.",
        )

    best = max(
        candidates,
        key=lambda x: (
            x["score"],
            x["type_match"],
            x["period_match"],
            x["keyword_coverage"],
        ),
    )

    status = status_for(best["score"], best["evidence_id"])
    reasoning_bits = [
        f"selected evidence {best['evidence_id']}",
        f"type_match={best['type_match']}",
        f"period_match={best['period_match']}",
        f"keyword_coverage={best['keyword_coverage']:.2f}",
    ]
    if best["exception_terms"]:
        reasoning_bits.append(
            "exception_terms=" + "|".join(best["exception_terms"])
        )

    return Assessment(
        control_id=str(control["control_id"]),
        best_evidence_id=best["evidence_id"],
        evidence_type_match=bool(best["type_match"]),
        period_match=bool(best["period_match"]),
        keyword_coverage=float(best["keyword_coverage"]),
        exception_terms=list(best["exception_terms"]),
        score=int(best["score"]),
        status=status,
        reasoning="; ".join(reasoning_bits),
    )
