from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

try:
    from .llm import make_reasoner
    from .loaders import load_controls, load_evidence_index, load_evidence_texts
    from .retrieval import VectorRetriever, build_documents
    from .scoring import assess_control
    from .trace import new_run_id, utc_now, write_jsonl
except ImportError:
    from llm import make_reasoner
    from loaders import load_controls, load_evidence_index, load_evidence_texts
    from retrieval import VectorRetriever, build_documents
    from scoring import assess_control
    from trace import new_run_id, utc_now, write_jsonl


def run_agentic_review(
    controls_path: str = "data/controls.csv",
    evidence_index_path: str = "data/evidence_index.csv",
    evidence_dir: str = "data/evidence",
    knowledge_base_dir: str = "data/knowledge_base",
    provider: str = "heuristic",
    model: str = "gpt-5-mini",
    top_k: int = 6,
) -> tuple[pd.DataFrame, list[dict]]:
    controls = load_controls(controls_path)
    evidence_index = load_evidence_index(evidence_index_path)
    evidence_texts = load_evidence_texts(evidence_index, evidence_dir)
    retriever = VectorRetriever(
        build_documents(
            controls,
            evidence_index,
            evidence_texts,
            knowledge_base_dir,
        )
    )
    reasoner = make_reasoner(provider=provider, model=model)
    run_id = new_run_id()
    traces: list[dict] = []
    rows: list[dict] = []

    for _, control in controls.iterrows():
        baseline = assess_control(control, evidence_index, evidence_texts)

        query = (
            f"{control['title']} {control['requirement']} "
            f"{control['required_evidence_type']} {control['keywords']}"
        )
        retrieved = retriever.retrieve(
            query,
            k=top_k,
            document_types={"control", "evidence", "knowledge"},
        )

        # Always include the exact control and deterministic best evidence in
        # context so an LLM cannot lose the most relevant grounded sources.
        required_ids = [f"control:{control['control_id']}"]
        if baseline.best_evidence_id:
            required_ids.append(f"evidence:{baseline.best_evidence_id}")
        by_id = {item.source_id: item for item in retrieved}
        for source_id in required_ids:
            exact = retriever.get(source_id)
            if exact is not None:
                by_id[source_id] = exact
        retrieved = sorted(
            by_id.values(),
            key=lambda item: item.score,
            reverse=True,
        )

        decision = reasoner.reason(control, baseline, retrieved)
        allowed = {item.source_id for item in retrieved}
        invalid_citations = [
            citation
            for citation in decision.citations
            if citation not in allowed
        ]
        citation_valid = not invalid_citations

        evidence_ids = set(evidence_index["evidence_id"].astype(str))
        invalid_evidence_ids = [
            evidence_id
            for evidence_id in decision.evidence_ids
            if evidence_id not in evidence_ids
        ]
        grounded = citation_valid and not invalid_evidence_ids

        row = asdict(decision)
        row.update(
            {
                "run_id": run_id,
                "baseline_status": baseline.status,
                "baseline_score": baseline.score,
                "citation_valid": citation_valid,
                "grounded": grounded,
                "review_status": "pending",
            }
        )
        rows.append(row)

        traces.append(
            {
                "timestamp": utc_now(),
                "run_id": run_id,
                "event": "agent_decision",
                "control_id": str(control["control_id"]),
                "provider": decision.provider,
                "query": query,
                "retrieved_sources": [
                    {
                        "source_id": item.source_id,
                        "document_type": item.document_type,
                        "score": item.score,
                    }
                    for item in retrieved
                ],
                "baseline": {
                    "status": baseline.status,
                    "score": baseline.score,
                    "reasoning": baseline.reasoning,
                },
                "decision": asdict(decision),
                "validation": {
                    "citation_valid": citation_valid,
                    "invalid_citations": invalid_citations,
                    "invalid_evidence_ids": invalid_evidence_ids,
                    "grounded": grounded,
                },
            }
        )

    return pd.DataFrame(rows), traces


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["heuristic", "openai"], default="heuristic")
    parser.add_argument("--model", default="gpt-5-mini")
    parser.add_argument("--output", default="output/agent_decisions.json")
    parser.add_argument("--trace", default="output/trace.jsonl")
    args = parser.parse_args()

    decisions, traces = run_agentic_review(
        provider=args.provider,
        model=args.model,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(decisions.to_dict(orient="records"), indent=2),
        encoding="utf-8",
    )
    write_jsonl(args.trace, traces)

    summary = {
        "controls": int(len(decisions)),
        "grounded": int(decisions["grounded"].sum()),
        "pending_human_review": int(
            (decisions["review_status"] == "pending").sum()
        ),
        "provider": args.provider,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
