import { Bookmark, Check, MessageSquareText, Pause, Play, Tag } from "lucide-react";
import { useState } from "react";
import type { Code, Segment } from "../types";

interface TranscriptPanelProps {
  segments: Segment[];
  selectedId: string | null;
  codes: Code[];
  onSelect: (segment: Segment) => void;
  onApplyCode: (codeId: string, segmentId: string) => Promise<void>;
  onMemo: (segmentId: string) => Promise<void>;
}

export function TranscriptPanel({ segments, selectedId, codes, onSelect, onApplyCode, onMemo }: TranscriptPanelProps) {
  const [playing, setPlaying] = useState(false);
  const [applied, setApplied] = useState<string[]>([]);

  async function applyCode(codeId: string, segmentId: string) {
    await onApplyCode(codeId, segmentId);
    setApplied((current) => [...current, `${codeId}:${segmentId}`]);
  }

  return (
    <section className="transcript-panel" aria-labelledby="transcript-heading">
      <div className="media-header">
        <div>
          <p className="section-kicker">Now reviewing</p>
          <h2 id="transcript-heading">Community interview 01</h2>
        </div>
        <span className="media-duration">48:16</span>
      </div>
      <div className="transport" aria-label="Media playback controls">
        <button className="play-button" type="button" onClick={() => setPlaying((value) => !value)} aria-label={playing ? "Pause" : "Play"}>
          {playing ? <Pause size={17} fill="currentColor" /> : <Play size={17} fill="currentColor" />}
        </button>
        <span className="transport-time">00:38</span>
        <div className="waveform" aria-hidden="true">
          {Array.from({ length: 76 }, (_, index) => (
            <i className={index < 24 ? "played" : ""} key={index} style={{ height: `${20 + ((index * 29) % 65)}%` }} />
          ))}
        </div>
        <span className="transport-time muted">48:16</span>
      </div>
      <div className="transcript-scroll">
        {segments.map((segment) => {
          const selected = segment.id === selectedId;
          return (
            <article className={`transcript-segment${selected ? " selected" : ""}`} key={segment.id} onClick={() => onSelect(segment)}>
              <button className="timestamp" type="button" onClick={() => onSelect(segment)}>{formatTime(segment.start_ms)}</button>
              <div className="segment-content">
                <div className="speaker-line">
                  <strong>{segment.speaker ?? "Unknown speaker"}</strong>
                  {segment.confidence && <span>{Math.round(segment.confidence * 100)}% confidence</span>}
                </div>
                <p>{segment.text}</p>
                {selected && (
                  <div className="segment-tools">
                    <span><Tag size={14} /> Apply code</span>
                    {codes.map((code) => {
                      const isApplied = applied.includes(`${code.id}:${segment.id}`);
                      return (
                        <button
                          type="button"
                          key={code.id}
                          className="code-chip"
                          style={{ "--code-color": code.color } as React.CSSProperties}
                          onClick={(event) => { event.stopPropagation(); void applyCode(code.id, segment.id); }}
                        >
                          {isApplied && <Check size={12} />} {code.name}
                        </button>
                      );
                    })}
                    <button className="tool-button" type="button" onClick={(event) => { event.stopPropagation(); void onMemo(segment.id); }}>
                      <MessageSquareText size={14} /> Memo
                    </button>
                    <button className="tool-button" type="button"><Bookmark size={14} /> Save</button>
                  </div>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function formatTime(milliseconds: number): string {
  const seconds = Math.floor(milliseconds / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

