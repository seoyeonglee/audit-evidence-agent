from langgraph.graph import START, END, StateGraph
from .schemas import GraphState
from . import nodes


def build_graph(checkpointer, provider="heuristic"):
    if provider != "heuristic":
        raise ValueError("Enterprise offline profile allows heuristic reasoning only")
    graph = StateGraph(GraphState)
    names = [
        "load_snapshot",
        "guardrails",
        "retrieve",
        "assess",
        "validate_grounding",
        "human_review",
        "finalize_report",
    ]
    for name in names:
        graph.add_node(name, getattr(nodes, name))
    graph.add_edge(START, names[0])
    for a, b in zip(names, names[1:]):
        if a != "validate_grounding":
            graph.add_edge(a, b)
    graph.add_node("grounding_failed", nodes.grounding_failed)
    graph.add_conditional_edges(
        "validate_grounding",
        lambda state: (
            "human_review" if state["grounding"]["valid"] else "grounding_failed"
        ),
        ["human_review", "grounding_failed"],
    )
    graph.add_edge("grounding_failed", "human_review")
    graph.add_edge(names[-1], END)
    return graph.compile(checkpointer=checkpointer)
