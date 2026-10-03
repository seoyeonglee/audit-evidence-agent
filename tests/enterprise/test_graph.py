import json
import subprocess
import sys
import pytest
from src.enterprise.registry import RunRegistry


def configured(f):
    store, svc, users, _, _, root = f
    r = RunRegistry(store).start(
        users["reviewer"], "REQ-ACCESS", 2, "heuristic", "graph"
    )
    return r, root / "checkpoints"


def test_real_graph_reaches_human_interrupt(enterprise_fixture):
    from src.enterprise.graph import build_graph
    from src.enterprise.checkpoints import CheckpointManager

    r, root = configured(enterprise_fixture)
    with CheckpointManager(root).open("demo-acme") as saver:
        g = build_graph(saver)
        result = g.invoke(
            {"run_id": r["id"], "snapshot": r["snapshot"]},
            {"configurable": {"thread_id": r["id"]}},
        )
        assert result["__interrupt__"]
        assert result["grounding"]["valid"] is True
        assert result["assessment"]["recommendation"] == "approve"
        assert "report" not in result
        assert result["assessment"]["citations"]


def test_new_process_loads_waiting_checkpoint(enterprise_fixture):
    from src.enterprise.graph import build_graph
    from src.enterprise.checkpoints import CheckpointManager

    r, root = configured(enterprise_fixture)
    with CheckpointManager(root).open("demo-acme") as saver:
        build_graph(saver).invoke(
            {"run_id": r["id"], "snapshot": r["snapshot"]},
            {"configurable": {"thread_id": r["id"]}},
        )
    program = """
import sys,json
from pathlib import Path
from src.enterprise.graph import build_graph
from src.enterprise.checkpoints import CheckpointManager
from langgraph.types import Command
with CheckpointManager(Path(sys.argv[1])).open('demo-acme') as saver:
 g=build_graph(saver)
 config={'configurable':{'thread_id':sys.argv[2]}}
 assert g.get_state(config).next==('human_review',)
 out=g.invoke(Command(resume={'id':'authorized-command','decision':'approve','reviewer':'reviewer','feedback':'Sources verified','result_version':3}),config)
 print(json.dumps(out['report']))
"""
    completed = subprocess.run(
        [sys.executable, "-c", program, str(root), r["id"]],
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(completed.stdout)
    assert report["review"]["id"] == "authorized-command"
    assert report["review"]["decision"] == "approve"
    assert report["run_id"] == r["id"]


@pytest.mark.parametrize("mutation", ["citation", "digest", "span"])
def test_fabricated_or_altered_source_blocks_grounding(enterprise_fixture, mutation):
    from src.enterprise.nodes import validate_grounding, retrieve, assess

    r, _ = configured(enterprise_fixture)
    state = {"run_id": r["id"], "snapshot": r["snapshot"], "findings": []}
    state.update(retrieve(state))
    state.update(assess(state))
    if mutation == "citation":
        state["assessment"]["citations"].append("unrelated-document")
    if mutation == "digest":
        state["snapshot"]["documents"][0]["digest"] = "0" * 64
    if mutation == "span":
        state["sources"][0]["quote"] = "invented quote"
    assert validate_grounding(state)["grounding"]["valid"] is False


def test_context_only_contains_selected_request(enterprise_fixture):
    from src.enterprise.nodes import retrieve

    r, _ = configured(enterprise_fixture)
    state = {"snapshot": r["snapshot"]}
    sources = retrieve(state)["sources"]
    ids = {d["id"] for d in r["snapshot"]["documents"]}
    assert all(s["document_id"] in ids for s in sources if s["kind"] == "evidence")
    assert len({s["source_id"] for s in sources}) == len(sources)
    assert retrieve({"snapshot": {**r["snapshot"], "documents": []}})["sources"] == []


def test_invalid_grounding_takes_safe_conditional_path(enterprise_fixture):
    from src.enterprise.graph import build_graph
    from src.enterprise.checkpoints import CheckpointManager

    r, root = configured(enterprise_fixture)
    r["snapshot"]["documents"][0]["digest"] = "0" * 64
    with CheckpointManager(root).open("demo-acme") as saver:
        result = build_graph(saver).invoke(
            {"run_id": r["id"], "snapshot": r["snapshot"]},
            {"configurable": {"thread_id": r["id"]}},
        )
    assert result["grounding"]["valid"] is False
    assert result["assessment"]["recommendation"] == "needs_changes"
    assert "DOCUMENT_DIGEST_MISMATCH" in result["assessment"]["missing_evidence"]
    assert result["__interrupt__"]
