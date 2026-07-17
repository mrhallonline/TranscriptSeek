"""Versioned JSON-lines IPC service; never opens a network socket."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, TextIO

from .importers import ImportedSegment, load_transcript
from .vault import ProjectVault


IPC_VERSION = 1


class LocalService:
    def __init__(self) -> None:
        self.vault: ProjectVault | None = None

    def _open_vault(self) -> ProjectVault:
        if not self.vault or not self.vault.is_open:
            raise RuntimeError("No project vault is open")
        return self.vault

    def dispatch(self, action: str, payload: dict[str, Any]) -> Any:
        if action == "health":
            return {"ipc_version": IPC_VERSION, "vault_open": bool(self.vault and self.vault.is_open), "network": "disabled"}
        if action == "create_project":
            self._close_current()
            self.vault = ProjectVault.create(
                payload["path"], payload["passphrase"], name=payload["name"],
                irb_protocol=payload.get("irb_protocol"), retention_date=payload.get("retention_date"),
                consent_restrictions=payload.get("consent_restrictions"),
                export_warning=payload.get("export_warning"),
            )
            return self.vault.summary()
        if action == "open_demo":
            self._close_current()
            demo_path = Path(tempfile.gettempdir()) / "transcriptseek-synthetic-demo.tsvault"
            demo_path.unlink(missing_ok=True)
            self.vault = ProjectVault.create(
                demo_path,
                "synthetic-demo-session-only",
                name="Community voice study",
                irb_protocol="SYNTHETIC-DEMO",
                retention_date="2027-12-31",
                consent_restrictions="Synthetic demonstration data only",
                export_warning="Review excerpts before export.",
            )
            segments = [
                ImportedSegment(12_400, 24_100, "What built trust was seeing the same neighbors return, week after week, to listen.", "Participant 1", 0.96),
                ImportedSegment(24_100, 38_800, "Can you tell me what changed after those conversations?", "Interviewer", 0.99),
                ImportedSegment(38_800, 56_300, "People started sharing decisions earlier. It felt less like consultation and more like ownership.", "Participant 1", 0.92),
                ImportedSegment(56_300, 69_100, "Trust takes repetition. A single meeting is not a relationship.", "Participant 4", 0.94),
            ]
            self.vault.add_transcript("Community interview 01", segments, source_format="synthetic", language="en")
            self.vault.create_code("Trust", "How trust is established or lost", color="#92e3a9")
            self.vault.create_code("Shared power", "Decision-making and ownership", color="#f4bc72")
            self.vault.create_code("Barriers", "Obstacles to participation", color="#d98cac")
            return self.vault.summary()
        if action == "open_project":
            self._close_current()
            self.vault = ProjectVault.open(payload["path"], payload["passphrase"])
            return self.vault.summary()
        if action == "lock_project":
            self._close_current()
            return {"locked": True}

        vault = self._open_vault()
        if action == "summary":
            return vault.summary()
        if action == "list_segments":
            return vault.list_segments(payload.get("transcript_id"))
        if action == "search":
            if payload.get("mode") == "hybrid":
                return vault.hybrid_search(payload["query"], speaker=payload.get("speaker"), limit=payload.get("limit", 100))
            return vault.search(payload["query"], speaker=payload.get("speaker"), limit=payload.get("limit", 100))
        if action == "import_transcript":
            path = Path(payload["path"])
            segments = load_transcript(path, format_name=payload.get("format"))
            return vault.add_transcript(
                payload.get("display_name", path.name), segments,
                source_format=payload.get("format", path.suffix.removeprefix(".")),
                language=payload.get("language"), source_bytes=path.read_bytes(),
            )
        if action == "import_segments":
            segments = [ImportedSegment(**segment) for segment in payload["segments"]]
            return vault.add_transcript(
                payload["display_name"], segments,
                source_format=payload.get("format", "json"), language=payload.get("language"),
            )
        if action == "list_codes":
            return vault.list_codes()
        if action == "create_code":
            return {"id": vault.create_code(payload["name"], payload.get("description", ""), parent_id=payload.get("parent_id"), color=payload.get("color", "#6f7bf7"))}
        if action == "apply_code":
            return {"id": vault.apply_code(payload["code_id"], payload["segment_id"], note=payload.get("note", ""))}
        if action == "create_memo":
            return {"id": vault.create_memo(payload["title"], payload["body"], segment_id=payload.get("segment_id"))}
        if action == "run_analyzer":
            return vault.run_analyzer(payload["analyzer_id"], payload.get("parameters"))
        if action == "detect_redactions":
            return vault.detect_redactions()
        if action == "list_redactions":
            return vault.list_redactions()
        if action == "review_redaction":
            vault.review_redaction(payload["candidate_id"], status=payload["status"], replacement=payload.get("replacement"))
            return {"reviewed": True}
        if action == "export_json":
            destination = Path(payload["path"])
            destination.write_bytes(vault.export_json())
            return {"path": str(destination), "bytes": destination.stat().st_size}
        if action == "export_csv":
            destination = Path(payload["path"])
            destination.write_bytes(vault.export_segments_csv())
            return {"path": str(destination), "bytes": destination.stat().st_size}
        if action in {"export_srt", "export_vtt"}:
            destination = Path(payload["path"])
            content = vault.export_srt(payload["transcript_id"], redacted=payload.get("redacted", False)) if action == "export_srt" else vault.export_vtt(payload["transcript_id"], redacted=payload.get("redacted", False))
            destination.write_bytes(content)
            return {"path": str(destination), "bytes": destination.stat().st_size}
        if action == "export_refi_codebook":
            destination = Path(payload["path"])
            destination.write_bytes(vault.export_refi_codebook())
            return {"path": str(destination), "bytes": destination.stat().st_size}
        if action == "import_refi_codebook":
            return {"code_ids": vault.import_refi_codebook(Path(payload["path"]).read_bytes())}
        raise ValueError(f"Unknown IPC action: {action}")

    def _close_current(self) -> None:
        if self.vault:
            self.vault.close()
            self.vault = None


def serve(input_stream: TextIO, output_stream: TextIO) -> None:
    service = LocalService()
    for line in input_stream:
        request_id: str | int | None = None
        try:
            request = json.loads(line)
            request_id = request.get("id")
            if request.get("version") != IPC_VERSION:
                raise ValueError(f"Unsupported IPC version: {request.get('version')}")
            result = service.dispatch(request["action"], request.get("payload", {}))
            response = {"id": request_id, "ok": True, "result": result}
        except Exception as exc:
            # No transcript text or stack trace crosses the IPC boundary.
            response = {"id": request_id, "ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}}
        output_stream.write(json.dumps(response, separators=(",", ":")) + "\n")
        output_stream.flush()


def main() -> None:
    serve(sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
