from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from datetime import datetime, timezone

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.agentic import run_agentic_review
from src.evaluate import evaluate_predictions
from src.loaders import load_controls, load_evidence_index, load_evidence_texts
from src.retrieval import VectorRetriever, build_documents
from src.scoring import assess_control

ROOT = Path(__file__).resolve().parents[1]
CONTROLS = ROOT / "data" / "controls.csv"
EVIDENCE_INDEX = ROOT / "data" / "evidence_index.csv"
EVIDENCE_DIR = ROOT / "data" / "evidence"
KNOWLEDGE = ROOT / "data" / "knowledge_base"
EXPECTED = ROOT / "eval" / "expected_outputs.csv"


class ReviewRequest(BaseModel):
    decision: Literal["approve", "needs_changes", "reject"]
    feedback: str = Field(default="", max_length=600)
    reviewer: str = Field(default="portfolio-reviewer", max_length=80)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@lru_cache(maxsize=1)
def build_state() -> dict:
    controls = load_controls(str(CONTROLS))
    evidence_index = load_evidence_index(str(EVIDENCE_INDEX))
    evidence_texts = load_evidence_texts(evidence_index, str(EVIDENCE_DIR))

    decisions, traces = run_agentic_review(
        controls_path=str(CONTROLS),
        evidence_index_path=str(EVIDENCE_INDEX),
        evidence_dir=str(EVIDENCE_DIR),
        knowledge_base_dir=str(KNOWLEDGE),
        provider="heuristic",
        top_k=6,
    )
    expected = pd.read_csv(EXPECTED)
    evaluation = evaluate_predictions(decisions, expected)

    retriever = VectorRetriever(
        build_documents(
            controls,
            evidence_index,
            evidence_texts,
            str(KNOWLEDGE),
        )
    )
    document_map = {doc.source_id: doc for doc in retriever.documents}
    trace_map = {item["control_id"]: item for item in traces}
    decision_map = {
        str(row["control_id"]): row
        for row in decisions.to_dict(orient="records")
    }

    baselines = {}
    for _, control in controls.iterrows():
        result = assess_control(control, evidence_index, evidence_texts)
        baselines[str(control["control_id"])] = result

    return {
        "controls": controls,
        "evidence_index": evidence_index,
        "evidence_texts": evidence_texts,
        "decisions": decisions,
        "decision_map": decision_map,
        "traces": traces,
        "trace_map": trace_map,
        "document_map": document_map,
        "baselines": baselines,
        "evaluation": evaluation,
        "reviews": {},
    }


def _clean(value):
    if pd.isna(value):
        return None
    return value


def _control_payload(control_id: str) -> dict:
    state = build_state()
    controls = state["controls"]
    matches = controls[controls["control_id"].astype(str) == control_id]
    if matches.empty:
        raise HTTPException(status_code=404, detail="Unknown synthetic control")

    control = matches.iloc[0]
    decision = state["decision_map"][control_id]
    trace = state["trace_map"][control_id]
    baseline = state["baselines"][control_id]

    retrieved_sources = []
    for item in trace["retrieved_sources"]:
        document = state["document_map"].get(item["source_id"])
        if not document:
            continue
        retrieved_sources.append(
            {
                "source_id": item["source_id"],
                "document_type": item["document_type"],
                "score": item["score"],
                "text": document.text,
                "cited": item["source_id"] in decision.get("citations", []),
            }
        )

    evidence = []
    evidence_ids = set(str(x) for x in decision.get("evidence_ids", []))
    if baseline.best_evidence_id:
        evidence_ids.add(str(baseline.best_evidence_id))

    evidence_index = state["evidence_index"]
    for evidence_id in sorted(evidence_ids):
        match = evidence_index[
            evidence_index["evidence_id"].astype(str) == evidence_id
        ]
        if match.empty:
            continue
        row = match.iloc[0]
        evidence.append(
            {
                "evidence_id": evidence_id,
                "filename": str(row["filename"]),
                "evidence_type": str(row["evidence_type"]),
                "period": str(row["period"]),
                "owner": str(row["owner"]),
                "text": state["evidence_texts"].get(evidence_id, ""),
            }
        )

    review = state["reviews"].get(
        control_id,
        {
            "status": "pending",
            "decision": None,
            "reviewer": None,
            "feedback": "",
            "timestamp": None,
        },
    )

    expected = pd.read_csv(EXPECTED)
    expected_row = expected[expected["control_id"].astype(str) == control_id]
    expected_status = (
        str(expected_row.iloc[0]["expected_status"])
        if not expected_row.empty
        else None
    )

    return {
        "control": {
            "control_id": control_id,
            "title": str(control["title"]),
            "requirement": str(control["requirement"]),
            "required_evidence_type": str(control["required_evidence_type"]),
            "target_period": str(control["target_period"]),
            "keywords": str(control["keywords"]).split("|"),
        },
        "decision": {
            **decision,
            "confidence": round(float(decision["confidence"]), 4),
            "baseline_score": int(decision["baseline_score"]),
            "citation_valid": bool(decision["citation_valid"]),
            "grounded": bool(decision["grounded"]),
        },
        "baseline": {
            "status": baseline.status,
            "score": int(baseline.score),
            "best_evidence_id": baseline.best_evidence_id or "",
            "evidence_type_match": bool(baseline.evidence_type_match),
            "period_match": bool(baseline.period_match),
            "keyword_coverage": round(float(baseline.keyword_coverage), 4),
            "exception_terms": list(baseline.exception_terms),
            "reasoning": baseline.reasoning,
        },
        "retrieval": {
            "query": trace["query"],
            "sources": retrieved_sources,
        },
        "evidence": evidence,
        "validation": trace["validation"],
        "review": review,
        "trace": {
            "run_id": trace["run_id"],
            "provider": trace["provider"],
            "timestamp": trace["timestamp"],
            "steps": [
                {
                    "id": "01",
                    "name": "Requirement parsed",
                    "detail": f"{control_id} · {control['required_evidence_type']} · {control['target_period']}",
                    "state": "complete",
                },
                {
                    "id": "02",
                    "name": "Deterministic guardrails",
                    "detail": f"{baseline.status.upper()} · score {baseline.score}",
                    "state": "complete",
                },
                {
                    "id": "03",
                    "name": "RAG retrieval",
                    "detail": f"{len(retrieved_sources)} sources retrieved",
                    "state": "complete",
                },
                {
                    "id": "04",
                    "name": "Agent assessment",
                    "detail": f"{str(decision['status']).upper()} · confidence {float(decision['confidence']):.2f}",
                    "state": "complete",
                },
                {
                    "id": "05",
                    "name": "Grounding validation",
                    "detail": "Citations valid" if decision["citation_valid"] else "Citation issue",
                    "state": "complete" if decision["grounded"] else "attention",
                },
                {
                    "id": "06",
                    "name": "Human review",
                    "detail": review["decision"] or "Pending reviewer decision",
                    "state": "complete" if review["status"] == "completed" else "pending",
                },
            ],
        },
        "expected_status": expected_status,
    }


app = FastAPI(
    title="Audit Evidence Agent API",
    version="2.0.0",
    description=(
        "Synthetic audit-evidence review API with deterministic guardrails, "
        "TF-IDF retrieval, heuristic agent reasoning, evaluation, human review, "
        "and end-to-end traceability."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "service": "audit-evidence-agent",
        "status": "ok",
        "mode": "synthetic-offline-rag",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    state = build_state()
    return {
        "status": "ok",
        "controls": int(len(state["controls"])),
        "provider": "heuristic-guardrail",
    }


@app.get("/api/v1/overview")
def overview():
    state = build_state()
    decisions = state["decisions"].copy()
    controls = state["controls"]

    queue = []
    for _, row in controls.iterrows():
        control_id = str(row["control_id"])
        decision = state["decision_map"][control_id]
        baseline = state["baselines"][control_id]
        review = state["reviews"].get(control_id)
        queue.append(
            {
                "control_id": control_id,
                "title": str(row["title"]),
                "status": str(decision["status"]),
                "confidence": round(float(decision["confidence"]), 4),
                "baseline_score": int(baseline.score),
                "grounded": bool(decision["grounded"]),
                "citation_valid": bool(decision["citation_valid"]),
                "review_status": "completed" if review else "pending",
                "review_decision": review["decision"] if review else None,
                "exception": str(decision.get("exception") or ""),
                "missing_count": len(decision.get("missing_evidence") or []),
            }
        )

    status_counts = decisions["status"].value_counts().to_dict()
    review_count = len(state["reviews"])

    return {
        "workspace": {
            "name": "Synthetic Internal Controls Review",
            "period": "Q3 2026",
            "framework": "Generic control-review guidance",
            "provider": "Heuristic RAG",
            "run_id": str(decisions.iloc[0]["run_id"]) if len(decisions) else "",
            "synthetic": True,
        },
        "summary": {
            "controls": int(len(decisions)),
            "supported": int(status_counts.get("supported", 0)),
            "partial": int(status_counts.get("partial", 0)),
            "gap": int(status_counts.get("gap", 0)),
            "missing": int(status_counts.get("missing", 0)),
            "grounded": int(decisions["grounded"].sum()),
            "pending_review": int(len(decisions) - review_count),
        },
        "evaluation": state["evaluation"],
        "queue": queue,
    }


@app.get("/api/v1/controls/{control_id}")
def control_detail(control_id: str):
    return _control_payload(control_id)


@app.post("/api/v1/controls/{control_id}/review")
def submit_review(control_id: str, payload: ReviewRequest):
    state = build_state()
    if control_id not in set(state["controls"]["control_id"].astype(str)):
        raise HTTPException(status_code=404, detail="Unknown synthetic control")

    record = {
        "status": "completed",
        "decision": payload.decision,
        "reviewer": payload.reviewer,
        "feedback": payload.feedback,
        "timestamp": utc_now(),
    }
    state["reviews"][control_id] = record
    return {
        "control_id": control_id,
        "review": record,
        "note": "Public demo review state is ephemeral and resets when the free service restarts.",
    }


@app.post("/api/v1/reviews/reset")
def reset_reviews():
    state = build_state()
    state["reviews"].clear()
    return {"status": "ok", "reviews": 0}

# v1 remains a public synthetic RAG sandbox. v2 has its own durable domain.
from src.platform.routes import create_router
import os
app.include_router(create_router(demo_enabled=os.environ.get('DEMO_MODE', '0') == '1'))

# Stateless, synthetic-only cloud evidence readiness workspace.
from src.cloud.assurance import router as cloud_assurance_router
app.include_router(cloud_assurance_router)
