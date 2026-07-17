import { useEffect, useState } from "react";
import { researchService } from "./service";
import type { Code, ProjectSummary, Segment } from "./types";
import { WelcomeScreen } from "./components/WelcomeScreen";
import { Workspace } from "./components/Workspace";

export function App() {
  const [summary, setSummary] = useState<ProjectSummary | null>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [codes, setCodes] = useState<Code[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.dataset.platform = navigator.platform.toLocaleLowerCase();
  }, []);

  async function openDemo() {
    setError(null);
    try {
      const [nextSummary, nextSegments, nextCodes] = await Promise.all([
        researchService.openDemo(),
        researchService.segments(),
        researchService.codes(),
      ]);
      setSummary(nextSummary);
      setSegments(nextSegments);
      setCodes(nextCodes);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to open the project.");
    }
  }

  async function lockProject() {
    await researchService.lock();
    setSummary(null);
    setSegments([]);
    setCodes([]);
  }

  if (!summary) {
    return <WelcomeScreen error={error} onOpenDemo={openDemo} />;
  }

  return (
    <Workspace
      summary={summary}
      initialSegments={segments}
      codes={codes}
      onLock={lockProject}
    />
  );
}

