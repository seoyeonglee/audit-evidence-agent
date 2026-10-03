from langgraph.types import interrupt
from src.platform.service import digest
from .context import scoped_sources


def load_snapshot(state):
    return {"snapshot": state["snapshot"]}


def guardrails(state):
    findings = list(state["snapshot"]["canonical"].get("exceptions", []))
    for doc in state["snapshot"]["documents"]:
        if not doc.get("extraction"):
            findings.append(
                {
                    "code": "UNSUPPORTED_DOCUMENT",
                    "message": "Unparsed evidence cannot be approved",
                }
            )
    return {"findings": findings}


def retrieve(state):
    return {"sources": scoped_sources(state["snapshot"])}


def assess(state):
    complete = state["snapshot"]["canonical"].get("complete", False)
    findings = state.get("findings", [])
    return {
        "assessment": {
            "provider": "offline-heuristic-v1",
            "recommendation": "approve"
            if complete and not findings
            else "needs_changes",
            "summary": "Required source facts are complete; independent human review is required."
            if complete and not findings
            else "Evidence gaps or conflicts require clarification before approval.",
            "citations": [s["source_id"] for s in state["sources"]],
            "missing_evidence": [f.get("message", f["code"]) for f in findings],
            "tool_policy": "retrieval-and-report-only",
        }
    }


def validate_grounding(state):
    docs = {d["id"]: d for d in state["snapshot"]["documents"]}
    known = {s["source_id"]: s for s in state["sources"]}
    failures = []
    for d in docs.values():
        if digest(d["content"]) != d["digest"]:
            failures.append("DOCUMENT_DIGEST_MISMATCH")
    for sid in state["assessment"]["citations"]:
        source = known.get(sid)
        if not source:
            failures.append("UNKNOWN_CITATION")
            continue
        doc = docs.get(source["document_id"])
        if (
            not doc
            or source["digest"] != doc["digest"]
            or not source["quote"]
            or source["quote"] not in doc["content"]
        ):
            failures.append("SOURCE_SPAN_MISMATCH")
            continue
        # Provenance line must point to the exact beginning of the cited span.
        pos = doc["content"].find(source["quote"])
        if doc["content"].count("\n", 0, pos) + 1 != source["line"]:
            failures.append("SOURCE_LINE_MISMATCH")
    if not state["assessment"]["citations"]:
        failures.append("NO_EVIDENCE_CITATIONS")
    return {
        "grounding": {
            "valid": not failures,
            "errors": sorted(set(failures)),
            "checked_sources": len(state["assessment"]["citations"]),
        }
    }


def grounding_failed(state):
    return {
        "assessment": {
            **state["assessment"],
            "recommendation": "needs_changes",
            "summary": "Source validation failed. Approval is blocked; request corrected evidence.",
            "missing_evidence": state["assessment"]["missing_evidence"]
            + state["grounding"]["errors"],
        }
    }


def human_review(state):
    command = interrupt(
        {
            "run_id": state["run_id"],
            "assessment": state["assessment"],
            "grounding": state["grounding"],
            "snapshot_version": state["snapshot"]["version"],
        }
    )
    return {"command": command}


def finalize_report(state):
    return {
        "report": {
            "schema_version": 1,
            "run_id": state["run_id"],
            "request_id": state["snapshot"]["request_id"],
            "snapshot_version": state["snapshot"]["version"],
            "control_id": state["snapshot"]["control_id"],
            "control_definition": state["snapshot"].get("control_definition", {}),
            "provider": state["assessment"]["provider"],
            "assessment": state["assessment"],
            "grounding": state["grounding"],
            "sources": state["sources"],
            "review": state["command"],
            "notice": "Synthetic reference workflow. Exact source checks do not prove semantic compliance.",
        }
    }
