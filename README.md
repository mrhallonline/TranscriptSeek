# TranscriptSeek

TranscriptSeek is a local-first desktop workbench for qualitative research with audio, video, and transcripts. It combines timestamped evidence retrieval, coding, memos, de-identification review, and transparent NLP without sending participant data to a cloud service.

> TranscriptSeek provides controls that can support an IRB-approved workflow; installing it does not itself make a study compliant. Researchers must follow their approved protocol and institutional policy.

## Current implementation

This repository now contains a tested vertical slice of the planned application:

- Authenticated encrypted project vaults with Argon2id, AES-256-GCM, atomic persistence, inactivity locking, and encrypted seekable media chunks.
- Immutable transcript versions; SRT, VTT, CSV, JSON, and untimed text ingestion; exact FTS and local hybrid vector retrieval.
- Hierarchical codebooks, passage coding, memos, append-only audit events, and reproducible analysis records.
- Frequency, n-gram, collocation, concordance, entity, keyphrase, topic-exploration, and explicitly limited lexical-sentiment analyzers.
- Human-reviewed identifier detection and reversible pseudonym replacements without modifying source transcripts.
- JSON, CSV, SRT, VTT, and REFI-QDA Codebook 1.0 import/export foundations.
- Verified offline model packages and an optional local `faster-whisper` transcription adapter that refuses remote model resolution.
- React/TypeScript research UI, Tauri shell, and versioned JSON-lines IPC over private process pipes—no application HTTP API.

The browser development build uses synthetic data. The Python IPC service and vault APIs implement real project creation, opening, import, search, coding, analysis, redaction, and export. Native file dialogs, complete REFI-QDA Project exchange, diarization, local-LLM workflows, signed installers, and institutional pilot validation remain release-hardening work.

## Development

Requirements:

- Python 3.11+
- Node.js 20+
- Rust stable and platform-specific Tauri prerequisites for the native shell

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,nlp]'
npm install

PYTHONPATH=src pytest
npm run build
npm run dev
```

The browser UI is then available on `http://127.0.0.1:1420`. It contains synthetic content only. To run the native shell after installing Rust:

```bash
npm run tauri dev
```

Local transcription support is deliberately separate because models are large:

```bash
python -m pip install -e '.[transcription]'
```

Only checksummed model directories with a TranscriptSeek `manifest.json` are accepted. Model installation must happen while all project vaults are locked.

## Private IPC service

The desktop shell keeps one Python sidecar alive and exchanges newline-delimited JSON through stdin/stdout. It never binds a network port. Every request includes an IPC version and correlation ID:

```json
{"id":1,"version":1,"action":"health","payload":{}}
```

Sensitive transcript text is excluded from error responses and audit metadata. For development:

```bash
PYTHONPATH=src python -m transcriptseek.ipc
```

## Security posture

- Project databases exist in plaintext only in process memory and are serialized to authenticated encrypted envelopes on disk.
- Imported media is copied into managed, independently authenticated encrypted chunks.
- The renderer has a restrictive content security policy and only the core Tauri capability set.
- There is no telemetry, cloud inference, external font, analytics, or remote crash-reporting code.
- Model files are installed from local packages after SHA-256 verification; the Whisper adapter sets `local_files_only`.
- Exports are intentionally plaintext research artifacts and require a researcher-controlled destination and disclosure review.

Read [the architecture](docs/ARCHITECTURE.md), [threat model](docs/THREAT_MODEL.md), and [release gaps](docs/RELEASE_GAPS.md) before evaluating TranscriptSeek with regulated data.

## Repository layout

```text
src/transcriptseek/   encrypted vault, research domain, NLP, exports, IPC
src/ui/               React research interface and Tauri adapter
src-tauri/            native shell, process bridge, minimal capabilities
tests/                synthetic security and workflow tests
docs/                 architecture, threat model, and release criteria
```

## License

See [LICENSE](LICENSE).
