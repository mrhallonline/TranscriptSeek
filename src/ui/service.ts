import type { AnalysisResult, Code, IpcRequest, ProjectSummary, Segment } from "./types";

const syntheticSegments: Segment[] = [
  {
    id: "segment_demo_1",
    transcript_id: "transcript_demo",
    source_name: "Community interview 01",
    start_ms: 12_400,
    end_ms: 24_100,
    speaker: "Participant 1",
    text: "What built trust was seeing the same neighbors return, week after week, to listen.",
    confidence: 0.96,
  },
  {
    id: "segment_demo_2",
    transcript_id: "transcript_demo",
    source_name: "Community interview 01",
    start_ms: 24_100,
    end_ms: 38_800,
    speaker: "Interviewer",
    text: "Can you tell me what changed after those conversations?",
    confidence: 0.99,
  },
  {
    id: "segment_demo_3",
    transcript_id: "transcript_demo",
    source_name: "Community interview 01",
    start_ms: 38_800,
    end_ms: 56_300,
    speaker: "Participant 1",
    text: "People started sharing decisions earlier. It felt less like consultation and more like ownership.",
    confidence: 0.92,
  },
  {
    id: "segment_demo_4",
    transcript_id: "transcript_demo",
    source_name: "Community interview 02",
    start_ms: 8_200,
    end_ms: 21_900,
    speaker: "Participant 4",
    text: "Trust takes repetition. A single meeting is not a relationship.",
    confidence: 0.94,
  },
];

const demoSummary: ProjectSummary = {
  project: {
    id: "project_demo",
    name: "Community voice study",
    irb_protocol: "SYNTHETIC-DEMO",
    retention_date: "2027-12-31",
    consent_restrictions: "Synthetic demonstration data only",
    export_warning: "Review excerpts before export.",
  },
  counts: { source_media: 2, transcript_version: 2, segment: 24, code: 3, coding: 7, memo: 2, analysis_run: 1 },
  analyzers: [
    { id: "frequency", version: "1.0.0", deterministic: true, limitations: "Counts do not capture context or meaning." },
    { id: "collocation", version: "1.0.0", deterministic: true, limitations: "Co-occurrence is not thematic importance." },
    { id: "keyphrase", version: "1.0.0", deterministic: true, limitations: "Suggestions require researcher interpretation." },
  ],
};

const demoCodes: Code[] = [
  { id: "code_trust", parent_id: null, name: "Trust", description: "How trust is established or lost", color: "#92e3a9" },
  { id: "code_power", parent_id: null, name: "Shared power", description: "Decision-making and ownership", color: "#f4bc72" },
  { id: "code_barrier", parent_id: null, name: "Barriers", description: "Obstacles to participation", color: "#d98cac" },
];

function isTauriRuntime(): boolean {
  return "__TAURI_INTERNALS__" in window;
}

async function tauriRequest<T>(request: IpcRequest): Promise<T> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<T>("ipc_request", { request });
}

async function demoRequest<T>({ action, payload = {} }: IpcRequest): Promise<T> {
  await new Promise((resolve) => window.setTimeout(resolve, 120));
  switch (action) {
    case "summary":
    case "open_demo":
      return demoSummary as T;
    case "list_segments":
      return syntheticSegments as T;
    case "list_codes":
      return demoCodes as T;
    case "search": {
      const query = String(payload.query ?? "").replace(/["*()]/g, "").toLocaleLowerCase();
      return syntheticSegments.filter((segment) => segment.text.toLocaleLowerCase().includes(query)) as T;
    }
    case "run_analyzer":
      return {
        run_id: "analysis_demo",
        input_hash: "c1431b1c…de81",
        manifest: demoSummary.analyzers.find((item) => item.id === payload.analyzer_id),
        output: {
          token_count: 79,
          items: [
            { term: "trust", count: 8 },
            { term: "relationship", count: 5 },
            { term: "ownership", count: 4 },
            { term: "conversations", count: 3 },
          ],
        },
      } as T;
    case "apply_code":
    case "create_memo":
      return { id: `demo_${Date.now()}` } as T;
    case "lock_project":
      return { locked: true } as T;
    default:
      throw new Error(`The browser demo does not implement ${action}.`);
  }
}

export async function request<T>(action: string, payload?: Record<string, unknown>): Promise<T> {
  const call = isTauriRuntime() ? tauriRequest : demoRequest;
  return call<T>({ action, payload });
}

export const researchService = {
  summary: () => request<ProjectSummary>("summary"),
  openDemo: () => request<ProjectSummary>("open_demo"),
  segments: () => request<Segment[]>("list_segments"),
  codes: () => request<Code[]>("list_codes"),
  search: (query: string) => request<Segment[]>("search", { query, mode: "hybrid" }),
  applyCode: (codeId: string, segmentId: string) => request<{ id: string }>("apply_code", { code_id: codeId, segment_id: segmentId }),
  createMemo: (title: string, body: string, segmentId?: string) => request<{ id: string }>("create_memo", { title, body, segment_id: segmentId }),
  analyze: (analyzerId: string) => request<AnalysisResult>("run_analyzer", { analyzer_id: analyzerId, parameters: { limit: 12 } }),
  lock: () => request<{ locked: boolean }>("lock_project"),
};
