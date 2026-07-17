export interface ProjectRecord {
  id: string;
  name: string;
  irb_protocol: string | null;
  retention_date: string | null;
  consent_restrictions: string | null;
  export_warning: string | null;
}

export interface ProjectSummary {
  project: ProjectRecord;
  counts: Record<string, number>;
  analyzers: AnalyzerManifest[];
}

export interface Segment {
  id: string;
  transcript_id: string;
  source_name: string;
  start_ms: number;
  end_ms: number;
  speaker: string | null;
  text: string;
  confidence: number | null;
  lexical_score?: number;
}

export interface Code {
  id: string;
  parent_id: string | null;
  name: string;
  description: string;
  color: string;
}

export interface AnalyzerManifest {
  id: string;
  version: string;
  deterministic: boolean;
  limitations: string;
}

export interface AnalysisResult {
  run_id: string;
  input_hash: string;
  manifest: AnalyzerManifest;
  output: {
    items?: Array<Record<string, unknown>>;
    token_count?: number;
  };
}

export interface IpcRequest {
  action: string;
  payload?: Record<string, unknown>;
}

