# Taking ownership of an existing product: first 90 days

This is a reusable operating approach, not a plan built from access to any company's internal code.

| Period | Work | Reviewable outcome | Decision gate |
|---|---|---|---|
| Days 1–15 | Read deployed topology and code; trace one real user workflow; map identity, data ownership and queue semantics | System map, data-flow diagram, dependency inventory, prioritized risks | Can the team explain where data and authorization decisions live? |
| Days 16–30 | Reproduce deployment; add baseline metrics and authorization regression tests; verify restore and rollback | Known-good release, restore evidence, initial latency/backlog/error baseline | Can a second engineer deploy and recover without undocumented steps? |
| Days 31–45 | Stabilize domain records and migration boundaries; resolve highest data-isolation risks | Canonical schema, reviewed RLS and role contracts, release gates | Are current user workflows protected during schema changes? |
| Days 46–60 | Build one complete asynchronous document path; validate model output and reviewer behavior | Input→job→facts→review lineage plus a labeled evaluation set | Is the automated output grounded, measurable and reversible before approval? |
| Days 61–75 | Measure the real bottleneck, introduce backpressure and supervise bad jobs | Workload-specific benchmark, queue runbook, capacity budget | Does a measured problem justify additional services or infrastructure? |
| Days 76–90 | Establish ownership, code review and hiring needs; reduce operational toil | Playbook, roadmap with cost/risk, onboarding walkthrough | What can the next engineer safely own without depending on one person? |

The first improvement should follow observed product pain, not a preferred technology rewrite. Existing external developers and specialists remain stakeholders: document interfaces, integration acceptance criteria and release ownership before changing team structure.
