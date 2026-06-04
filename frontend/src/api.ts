// API client + shared types mirroring the backend RunState shape.

export interface RunParams {
  date_range?: string | null;
  max_candidates: number;
  max_kept: number;
  source_set: string[];
  export_dir?: string | null;
  cost_cap_usd?: number | null;
}

export interface Stage { name: string; status: string; detail: string; }
export interface Counts {
  candidates: number; kept: number; rejected: number;
  verified: number; unsupported: number;
}
export interface ScopePlan { sub_questions: string[]; search_terms: string[]; rationale: string; }
export interface Candidate {
  source_id: string; title: string; authors: string[]; year: number | null;
  venue: string | null; abstract: string; identifier: string; url: string; source: string;
}
export interface RejectionEntry {
  source_id: string; title: string; reason_code: string; justification: string;
}
export interface CitationRef { marker: string; source_id: string; claim: string; }
export interface CitationVerdict { marker: string; source_id: string; claim: string; supported: boolean; reason: string; }
export interface SynthOutput {
  review_markdown: string; mermaid: string; citations: CitationRef[]; themes: string[];
}
export interface Outputs {
  review_markdown: string; mermaid: string; bibtex: string;
  citations_json: string; rejection_log: RejectionEntry[]; export_paths: string[];
}
export interface RunState {
  id: string; query: string; params: RunParams; status: string;
  created_at: string; updated_at: string;
  stages: Stage[]; counts: Counts;
  scope_plan: ScopePlan | null; plan_source_set: string[]; approved: boolean;
  candidates: Candidate[]; kept_ids: string[]; rejections: RejectionEntry[];
  synth: SynthOutput | null;
  verdicts: CitationVerdict[];
  outputs: Outputs;
  cost_usd: number; tokens_in: number; tokens_out: number; steps: number; error: string;
  verify_rounds: number;
}
export interface RunSummary {
  id: string; query: string; status: string; phase: string;
  cost_usd: number; created_at: string; updated_at: string;
}

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json();
}

export const api = {
  health: () => fetch("/health").then(j<any>),
  createRun: (query: string, params: RunParams) =>
    fetch("/api/runs", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, params }),
    }).then(j<RunState>),
  getRun: (id: string) => fetch(`/api/runs/${id}`).then(j<RunState>),
  listRuns: () => fetch("/api/runs").then(j<RunSummary[]>),
  approve: (id: string) =>
    fetch(`/api/runs/${id}/approve`, { method: "POST" }).then(j<RunState>),
  revise: (id: string, plan: ScopePlan, source_set: string[]) =>
    fetch(`/api/runs/${id}/revise`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...plan, source_set }),
    }).then(j<RunState>),
  cancel: (id: string) =>
    fetch(`/api/runs/${id}/cancel`, { method: "POST" }).then(j<any>),
};

export const ACTIVE_STATUSES = new Set([
  "created", "scoping", "searching", "screening",
  "extracting", "synthesizing", "verifying", "assembling",
]);
export const SOURCES = ["arxiv", "semantic_scholar", "openalex", "web"];
