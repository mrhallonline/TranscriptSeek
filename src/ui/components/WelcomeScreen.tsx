import { FilePlus2, FolderLock, HardDrive, ShieldCheck } from "lucide-react";

interface WelcomeScreenProps {
  error: string | null;
  onOpenDemo: () => Promise<void>;
}

export function WelcomeScreen({ error, onOpenDemo }: WelcomeScreenProps) {
  return (
    <main className="welcome-shell">
      <section className="welcome-card" aria-labelledby="welcome-title">
        <div className="brand-mark" aria-hidden="true">TS</div>
        <p className="eyebrow">Private qualitative research</p>
        <h1 id="welcome-title">Listen closely.<br />Keep the evidence near.</h1>
        <p className="welcome-copy">
          Search, code, and analyze interview transcripts without sending participant data
          beyond this computer.
        </p>
        {error && <p className="error-banner" role="alert">{error}</p>}
        <div className="welcome-actions">
          <button className="button primary" type="button" onClick={onOpenDemo}>
            <FolderLock size={18} /> Open synthetic project
          </button>
          <button className="button secondary" type="button" disabled title="Available in the packaged desktop build">
            <FilePlus2 size={18} /> New encrypted project
          </button>
        </div>
        <div className="privacy-strip">
          <span><ShieldCheck size={16} /> Encrypted vaults</span>
          <span><HardDrive size={16} /> Local processing</span>
          <span className="offline-dot">No telemetry</span>
        </div>
      </section>
      <aside className="welcome-aside" aria-label="Research principles">
        <p className="aside-number">01</p>
        <h2>Evidence before inference.</h2>
        <p>Every suggestion returns to a speaker, a passage, and a moment in the recording.</p>
        <div className="wave-art" aria-hidden="true">
          {Array.from({ length: 32 }, (_, index) => <i key={index} style={{ height: `${14 + ((index * 17) % 66)}%` }} />)}
        </div>
      </aside>
    </main>
  );
}

