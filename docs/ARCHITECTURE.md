# Architecture

## Trust boundaries

```text
Tauri renderer (untrusted presentation)
        │ versioned invoke command
Tauri process bridge
        │ JSON lines over inherited stdin/stdout
Python research service (trusted local core)
        ├── plaintext SQLite only in process memory
        ├── encrypted vault envelope on disk
        ├── encrypted managed-media directory
        └── explicitly created plaintext exports
```

TranscriptSeek does not expose an application HTTP server. The Rust bridge correlates each renderer request with exactly one sidecar response. The Python service returns structured errors without stack traces or transcript content.

## Storage

The current storage adapter uses SQLite's in-memory serialization API and encrypts the complete database with AES-256-GCM. Each persistence operation derives an encryption key with Argon2id and a fresh salt, writes an authenticated envelope to a sibling temporary file, flushes it, and atomically replaces the prior vault. This preserves FTS indexes, redaction mappings, and audit records without writing plaintext SQLite pages.

This differs from the original SQLCipher proposal because SQLCipher is not available in the initial development environment. The public `ProjectVault` and IPC contracts isolate that choice. A later SQLCipher adapter must pass the same no-plaintext-residue and migration tests before replacement.

Managed media uses one random per-vault key stored inside the encrypted database. Files are split into independently authenticated AES-GCM chunks. This permits bounded decryption for seeking; a production media protocol still needs to connect those chunks to the native media element without writing temporary files.

## Research provenance

Imported transcript versions are immutable. Corrections create a child version containing a source hash and parent identifier. Each `AnalysisRun` records analyzer ID/version, parameters, input hash, optional model identity/hash, status, timestamps, and structured output. Generated or suggested interpretations are not confirmed codings.

Built-in analyzers implement one internal contract:

- Stable identifier and version.
- Deterministic status.
- Documented limitations.
- Structured parameters and results.
- A content-derived input hash.

The hashing-vector baseline is deterministic, computed in memory, and labeled with its provider. It is not represented as a deep semantic model. A local sentence-transformer can implement the same `EmbeddingProvider` protocol.

## Model boundary

Model packages contain a manifest with identity, engine, version, languages, limitations, and a SHA-256 digest for every file. Packages are verified before and after copying and cannot be installed while a vault is open. The Whisper adapter accepts only a verified local directory and passes `local_files_only=True`.

The application contains no arbitrary Python plugin loader. New analyzers must be reviewed and bundled as application code in v1.

