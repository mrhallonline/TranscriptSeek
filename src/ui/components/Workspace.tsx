import { Download, FileAudio, Lock, MoreHorizontal, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { researchService } from "../service";
import type { AnalysisResult, Code, ProjectSummary, Segment } from "../types";
import { AnalysisPanel } from "./AnalysisPanel";
import { PrivacyStatus } from "./PrivacyStatus";
import { SearchPanel } from "./SearchPanel";
import { TranscriptPanel } from "./TranscriptPanel";

interface WorkspaceProps {
  summary: ProjectSummary;
  initialSegments: Segment[];
  codes: Code[];
  onLock: () => Promise<void>;
}

export function Workspace({ summary, initialSegments, codes, onLock }: WorkspaceProps) {
  const [results, setResults] = useState(initialSegments);
  const [selected, setSelected] = useState<Segment | null>(initialSegments[0] ?? null);
  const [isSearching, setIsSearching] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  async function search(query: string) {
    setIsSearching(true);
    try {
      const next = query.trim() ? await researchService.search(query) : initialSegments;
      setResults(next);
      if (next[0]) setSelected(next[0]);
    } finally {
      setIsSearching(false);
    }
  }

  async function applyCode(codeId: string, segmentId: string) {
    await researchService.applyCode(codeId, segmentId);
    showToast("Code applied and recorded in the audit trail.");
  }

  async function createMemo(segmentId: string) {
    await researchService.createMemo("Passage memo", "Follow up during focused coding.", segmentId);
    showToast("Memo saved locally.");
  }

  function showToast(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(null), 2600);
  }

  return (
    <main className="workspace-shell">
      <header className="app-header">
        <div className="compact-brand"><span>TS</span><strong>TranscriptSeek</strong></div>
        <div className="project-title">
          <span className="project-icon"><FileAudio size={17} /></span>
          <div><strong>{summary.project.name}</strong><small>{summary.counts.source_media} sources · {summary.counts.segment} passages</small></div>
        </div>
        <PrivacyStatus protocol={summary.project.irb_protocol} />
        <div className="header-actions">
          <button className="button tertiary" type="button"><Download size={15} /> Export</button>
          <button className="icon-button" type="button" aria-label="More project actions"><MoreHorizontal size={18} /></button>
          <button className="button lock-button" type="button" onClick={() => void onLock()}><Lock size={15} /> Lock</button>
        </div>
      </header>
      <div className="research-grid">
        <SearchPanel results={results} isSearching={isSearching} onSearch={search} onSelect={setSelected} />
        <TranscriptPanel
          segments={initialSegments}
          selectedId={selected?.id ?? null}
          codes={codes}
          onSelect={setSelected}
          onApplyCode={applyCode}
          onMemo={createMemo}
        />
        <AnalysisPanel analyzers={summary.analyzers} codes={codes} onAnalyze={(id): Promise<AnalysisResult> => researchService.analyze(id)} />
      </div>
      <footer className="status-footer">
        <span><ShieldCheck size={13} /> All project material is encrypted at rest</span>
        <span>Local IPC v1</span>
        <span>Auto-lock in 14:32</span>
      </footer>
      {toast && <div className="toast" role="status">{toast}</div>}
    </main>
  );
}

