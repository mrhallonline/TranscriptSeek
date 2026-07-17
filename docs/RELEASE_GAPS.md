# Release gaps

The repository is an executable, tested vertical slice—not a production certification. Do not use it with regulated participant data until the applicable institution has reviewed the completed controls.

## Required before a sensitive-data pilot

- Install Rust and compile/test the Tauri bridge on supported macOS and Windows versions.
- Bundle the Python sidecar and native dependencies; sign and notarize installers.
- Add native project creation/opening, file import, explicit export confirmation, backup/restore, and passphrase-change flows.
- Connect encrypted media chunks to a seekable custom Tauri protocol and verify no plaintext media files are created.
- Add schema migrations, rollback fixtures, crash recovery, disk-space handling, and encrypted media backup.
- Implement complete REFI-QDA Project import/export and validate every QDPX fixture. Codebook 1.0 import/export is schema-validated, but project exchange is not yet implemented.
- Add speaker diarization and alignment behind verified offline model packages.
- Add local generative Q&A/summarization only after every substantive claim can be enforced to carry segment/timestamp evidence.
- Perform macOS and Windows outbound-traffic, temporary-file, swap, crash-dump, dependency, and installer audits.
- Benchmark the 100-hour corpus performance target and evaluate retrieval, transcription, diarization, and identifier detection on approved synthetic/public datasets.
- Complete keyboard, screen-reader, high-contrast, localization, and reduced-motion testing.
- Conduct independent security review and a qualitative-researcher pilot using synthetic or non-sensitive material.

## Deferred product scope

- Multi-user accounts, shared lab servers, concurrent coding, and inter-coder reconciliation.
- Cloud synchronization, external model APIs, arbitrary plugins, and remote collaboration.
- Automatic interpretation or publication of research findings.
