import { request } from "./platform";
import type { Session, Run, EvidenceRequest } from "./types";
export const enterprise = {
  session: (persona: string) =>
    request<Session>("POST", "/api/v2/demo/session", undefined, { persona }),
  requests: (token: string) =>
    request<{ requests: EvidenceRequest[] }>("GET", "/api/v2/requests", token),
  scenario: (token: string, scenario: string) =>
    request<EvidenceRequest>("POST", "/api/v2/demo/agent-scenario", token, {
      scenario,
    }),
  start: (token: string, r: EvidenceRequest) =>
    request<Run>(
      "POST",
      `/api/v2/requests/${r.id}/agent-runs`,
      token,
      { version: r.version },
      crypto.randomUUID(),
    ),
  runs: (token: string, id: string) =>
    request<{ runs: Run[] }>("GET", `/api/v2/requests/${id}/agent-runs`, token),
  detail: (token: string, id: string) =>
    request<Run>("GET", `/api/v2/agent-runs/${id}`, token),
  process: (token: string) =>
    request("POST", "/api/v2/demo/agent-process", token, {}),
  review: (
    token: string,
    r: Run,
    decision: string,
    feedback: string,
    key: string,
  ) =>
    request(
      "POST",
      `/api/v2/agent-runs/${r.id}/review`,
      token,
      { version: r.snapshot_version, decision, feedback },
      key,
    ),
  report: (token: string, id: string) =>
    request("GET", `/api/v2/agent-runs/${id}/report`, token),
};
