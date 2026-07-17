import { Atom, ChevronRight, Fingerprint, Info, LoaderCircle, Sparkles } from "lucide-react";
import { useState } from "react";
import type { AnalysisResult, AnalyzerManifest, Code } from "../types";

interface AnalysisPanelProps {
  analyzers: AnalyzerManifest[];
  codes: Code[];
  onAnalyze: (analyzerId: string) => Promise<AnalysisResult>;
}

export function AnalysisPanel({ analyzers, codes, onAnalyze }: AnalysisPanelProps) {
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [running, setRunning] = useState<string | null>(null);

  async function run(analyzerId: string) {
    setRunning(analyzerId);
    try {
      setResult(await onAnalyze(analyzerId));
    } finally {
      setRunning(null);
    }
  }

  return (
    <aside className="analysis-panel" aria-labelledby="analysis-heading">
      <div className="panel-heading compact-heading">
        <div>
          <p className="section-kicker">Local NLP workbench</p>
          <h2 id="analysis-heading">Analysis</h2>
        </div>
        <Atom size={20} aria-hidden="true" />
      </div>
      <section className="analysis-block">
        <h3>Project codebook <span>{codes.length}</span></h3>
        <div className="codebook-list">
          {codes.map((code) => (
            <button type="button" key={code.id}>
              <i style={{ background: code.color }} />
              <span><strong>{code.name}</strong><small>{code.description}</small></span>
              <ChevronRight size={14} />
            </button>
          ))}
        </div>
      </section>
      <section className="analysis-block">
        <h3>Transparent analyzers</h3>
        <div className="analyzer-grid">
          {analyzers.map((analyzer) => (
            <button type="button" key={analyzer.id} onClick={() => void run(analyzer.id)} disabled={running !== null}>
              {running === analyzer.id ? <LoaderCircle className="spin" size={16} /> : <Sparkles size={16} />}
              <span>{humanize(analyzer.id)}</span>
              <small>v{analyzer.version}</small>
            </button>
          ))}
        </div>
      </section>
      {result ? (
        <section className="analysis-result" aria-live="polite">
          <div className="result-title">
            <div><Fingerprint size={15} /><strong>{humanize(result.manifest.id)}</strong></div>
            <span>Reproducible</span>
          </div>
          <div className="term-list">
            {result.output.items?.slice(0, 6).map((item) => (
              <div key={JSON.stringify(item)}>
                <span>{String(item.term ?? (item.terms as string[] | undefined)?.join(" + ") ?? "Result")}</span>
                <strong>{String(item.count ?? item.pmi ?? "")}</strong>
              </div>
            ))}
          </div>
          <p className="limitation"><Info size={13} /> {result.manifest.limitations}</p>
          <code>input {result.input_hash.slice(0, 12)}</code>
        </section>
      ) : (
        <div className="analysis-empty">
          <Fingerprint size={24} />
          <p>Run an analyzer to create a versioned, traceable research artifact.</p>
        </div>
      )}
    </aside>
  );
}

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/^./, (character) => character.toLocaleUpperCase());
}

