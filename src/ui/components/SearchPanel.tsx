import { Search, SlidersHorizontal, X } from "lucide-react";
import { useState } from "react";
import type { Segment } from "../types";

interface SearchPanelProps {
  results: Segment[];
  isSearching: boolean;
  onSearch: (query: string) => Promise<void>;
  onSelect: (segment: Segment) => void;
}

export function SearchPanel({ results, isSearching, onSearch, onSelect }: SearchPanelProps) {
  const [query, setQuery] = useState("");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSearch(query);
  }

  return (
    <section className="search-panel" aria-labelledby="search-heading">
      <div className="panel-heading compact-heading">
        <div>
          <p className="section-kicker">Corpus retrieval</p>
          <h2 id="search-heading">Search</h2>
        </div>
        <button className="icon-button" type="button" title="Search filters" aria-label="Search filters">
          <SlidersHorizontal size={17} />
        </button>
      </div>
      <form className="search-form" onSubmit={submit}>
        <button className="search-submit" type="submit" aria-label="Run transcript search">
          <Search size={17} aria-hidden="true" />
        </button>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="phrase, Boolean, proximity…"
          aria-label="Search transcripts"
        />
        {query && (
          <button className="search-clear" type="button" onClick={() => setQuery("")} aria-label="Clear search">
            <X size={15} />
          </button>
        )}
      </form>
      <p className="result-count" aria-live="polite">
        {isSearching ? "Searching locally…" : `${results.length} evidence ${results.length === 1 ? "passage" : "passages"}`}
      </p>
      <div className="search-results">
        {results.map((segment) => (
          <button className="search-result" type="button" key={segment.id} onClick={() => onSelect(segment)}>
            <span className="result-meta">
              <strong>{formatTime(segment.start_ms)}</strong>
              <span>{segment.speaker ?? "Unknown speaker"}</span>
            </span>
            <span className="result-text">{segment.text}</span>
            <span className="source-name">{segment.source_name}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function formatTime(milliseconds: number): string {
  const seconds = Math.floor(milliseconds / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}
