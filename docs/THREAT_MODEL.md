# Threat model

Last reviewed: 2026-07-17

## Protected assets

- Participant audio, video, transcripts, identifiers, pseudonym mappings, annotations, codes, and memos.
- Study metadata such as protocol numbers, consent restrictions, and retention dates.
- Research integrity: transcript lineage, analyzer provenance, coding decisions, and audit history.

## In-scope threats and controls

| Threat | Initial controls | Remaining release work |
| --- | --- | --- |
| Lost or stolen device | Passphrase-derived authenticated vault, encrypted managed media, auto-lock | Independent cryptographic review; keychain policy decision |
| Incorrect passphrase or modified vault | Argon2id plus AES-GCM authentication; fail-closed tests | Recovery-key workflow, if institutionally approved |
| Plaintext database residue | SQLite exists only in memory; encrypted atomic persistence; no plaintext FTS/vector indexes | OS swap and crash-dump guidance; platform forensic testing |
| Accidental cloud disclosure | No cloud APIs, telemetry, remote fonts, or public HTTP service; restrictive CSP | Packaged-binary traffic audit on macOS and Windows |
| Model supply-chain attack | Offline package manifests and per-file SHA-256 verification; install only while locked | Signed model manifests and curated distribution process |
| Sensitive logs or errors | Audit metadata excludes transcript text; IPC errors omit tracebacks | Automated log-content scanning in packaged builds |
| Accidental export disclosure | Exports are explicit and project metadata can carry warnings | Native disclosure confirmation and destination validation |
| Misleading NLP conclusions | Analyzer limitations, deterministic provenance, suggestion review states | Researcher usability study and model-card interface |
| Missed identifiers | Conservative detector plus mandatory human review; original remains immutable | Evaluate multilingual NER and identifier recall on approved synthetic benchmarks |
| Malicious renderer content | Tauri command allowlist, core-only capability, CSP, no external content | Rust dependency audit and penetration testing |

## Explicitly out of scope

- A malicious administrator or attacker with control of the running operating system.
- Screen capture, shoulder surfing, hardware keyloggers, or compromised firmware.
- Protection of a plaintext export after it leaves TranscriptSeek.
- Multi-user authorization, concurrent editing, or network collaboration.
- A guarantee that automated de-identification finds every identifier.
- Institutional, legal, or IRB certification.

## Security invariants

1. Opening a vault never requires network access.
2. No project operation deliberately initiates an outbound connection.
3. Wrong passphrases and authenticated-data changes fail closed.
4. Original transcript versions and source media are never mutated by correction or redaction.
5. Model installation is unavailable while sensitive project material is open.
6. NLP output is traceable to input hashes, versions, parameters, and source timestamps.
7. Plaintext export is an explicit boundary crossing, not an automatic background action.

## Incident handling

Do not place participant content, vault passphrases, or decrypted database material in issue reports. Preserve the encrypted vault and application version, record the action and time, disconnect the affected workstation if institutional policy requires it, and follow the study's approved incident-response process.

