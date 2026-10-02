export type QueueItem = {
  control_id: string;
  title: string;
  status: string;
  confidence: number;
  baseline_score: number;
  grounded: boolean;
  citation_valid: boolean;
  review_status: string;
  review_decision: string | null;
  exception: string;
  missing_count: number;
};

export type Overview = {
  workspace: {
    name: string;
    period: string;
    framework: string;
    provider: string;
    run_id: string;
    synthetic: boolean;
  };
  summary: {
    controls: number;
    supported: number;
    partial: number;
    gap: number;
    missing: number;
    grounded: number;
    pending_review: number;
  };
  evaluation: Record<string, number>;
  queue: QueueItem[];
};

export type Source = {
  source_id: string;
  document_type: string;
  score: number;
  text: string;
  cited: boolean;
};

export type Evidence = {
  evidence_id: string;
  filename: string;
  evidence_type: string;
  period: string;
  owner: string;
  text: string;
};

export type Detail = {
  control: {
    control_id: string;
    title: string;
    requirement: string;
    required_evidence_type: string;
    target_period: string;
    keywords: string[];
  };
  decision: {
    control_id: string;
    status: string;
    confidence: number;
    requirement_summary: string;
    evidence_ids: string[];
    citations: string[];
    exception: string;
    missing_evidence: string[];
    reasoning: string;
    provider: string;
    run_id: string;
    baseline_status: string;
    baseline_score: number;
    citation_valid: boolean;
    grounded: boolean;
    review_status: string;
  };
  baseline: {
    status: string;
    score: number;
    best_evidence_id: string;
    evidence_type_match: boolean;
    period_match: boolean;
    keyword_coverage: number;
    exception_terms: string[];
    reasoning: string;
  };
  retrieval: {
    query: string;
    sources: Source[];
  };
  evidence: Evidence[];
  validation: {
    citation_valid: boolean;
    invalid_citations: string[];
    invalid_evidence_ids: string[];
    grounded: boolean;
  };
  review: {
    status: string;
    decision: string | null;
    reviewer: string | null;
    feedback: string;
    timestamp: string | null;
  };
  trace: {
    run_id: string;
    provider: string;
    timestamp: string;
    steps: Array<{ id: string; name: string; detail: string; state: string }>;
  };
  expected_status: string | null;
};
