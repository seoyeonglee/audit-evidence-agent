from typing import TypedDict


class RunSnapshot(TypedDict):
    request_id: str
    version: int
    control_id: str
    period: str
    title: str
    canonical: dict
    documents: list[dict]
    control_definition: dict
    guidance: str


class GraphState(TypedDict, total=False):
    run_id: str
    snapshot: RunSnapshot
    findings: list[dict]
    sources: list[dict]
    assessment: dict
    grounding: dict
    command: dict
    report: dict


Assessment = dict
ReviewCommand = dict
RunDetail = dict
