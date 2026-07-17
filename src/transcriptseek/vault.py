"""Encrypted project vault and research-domain operations."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import sqlite3
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

from .analyzers import ANALYZERS, AnalyzerContext, analysis_input_hash
from .crypto import decrypt_envelope, encrypt_envelope, encrypt_managed_file
from .exporters import export_refi_codebook, import_refi_codebook, segments_to_srt, segments_to_vtt
from .importers import ImportedSegment, validate_segments
from .redaction import detect_identifiers
from .schema import SCHEMA_SQL, SCHEMA_VERSION


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class VaultLockedError(RuntimeError):
    pass


class ProjectVault:
    """A SQLite research database that exists as plaintext only in memory.

    Each committed mutation is serialized and atomically persisted as an
    Argon2id/AES-GCM authenticated envelope. Managed media is separately chunk-
    encrypted so the desktop layer can implement seeking without decryption to disk.
    """

    def __init__(
        self,
        path: Path,
        connection: sqlite3.Connection,
        passphrase: str,
        *,
        auto_lock_seconds: int = 15 * 60,
    ) -> None:
        self.path = path
        self._connection: sqlite3.Connection | None = connection
        self._passphrase = bytearray(passphrase.encode("utf-8"))
        self.auto_lock_seconds = auto_lock_seconds
        self._last_activity = time.monotonic()

    @classmethod
    def create(
        cls,
        path: Path | str,
        passphrase: str,
        *,
        name: str,
        irb_protocol: str | None = None,
        retention_date: str | None = None,
        consent_restrictions: str | None = None,
        export_warning: str | None = None,
        auto_lock_seconds: int = 15 * 60,
    ) -> "ProjectVault":
        destination = Path(path)
        if destination.exists():
            raise FileExistsError(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        connection = cls._new_connection()
        connection.executescript(SCHEMA_SQL)
        project_id = new_id("project")
        now = utc_now()
        connection.execute(
            """INSERT INTO project
               (id, name, created_at, updated_at, irb_protocol, retention_date,
                consent_restrictions, export_warning, schema_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id,
                name.strip(),
                now,
                now,
                irb_protocol,
                retention_date,
                consent_restrictions,
                export_warning,
                SCHEMA_VERSION,
            ),
        )
        connection.execute("INSERT INTO vault_secret(name, value) VALUES ('media_key', ?)", (os.urandom(32),))
        connection.execute(
            """INSERT INTO audit_event
               (occurred_at, event_type, object_type, object_id, details_json)
               VALUES (?, 'created', 'project', ?, '{}')""",
            (now, project_id),
        )
        connection.commit()
        vault = cls(destination, connection, passphrase, auto_lock_seconds=auto_lock_seconds)
        vault.save()
        return vault

    @classmethod
    def open(
        cls,
        path: Path | str,
        passphrase: str,
        *,
        auto_lock_seconds: int = 15 * 60,
    ) -> "ProjectVault":
        source = Path(path)
        plaintext = decrypt_envelope(source.read_bytes(), passphrase)
        connection = cls._new_connection()
        connection.deserialize(plaintext)
        connection.execute("PRAGMA foreign_keys = ON")
        version = connection.execute("SELECT schema_version FROM project").fetchone()[0]
        if version != SCHEMA_VERSION:
            connection.close()
            raise RuntimeError(f"Unsupported vault schema {version}; expected {SCHEMA_VERSION}")
        return cls(source, connection, passphrase, auto_lock_seconds=auto_lock_seconds)

    @staticmethod
    def _new_connection() -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA trusted_schema = OFF")
        return connection

    @property
    def is_open(self) -> bool:
        return self._connection is not None

    def _require_open(self) -> sqlite3.Connection:
        if self._connection is None:
            raise VaultLockedError("The project vault is locked")
        if self.auto_lock_seconds > 0 and time.monotonic() - self._last_activity > self.auto_lock_seconds:
            # Every mutation is persisted immediately, so expiry can lock without
            # re-entering the activity check through save().
            self.close(save=False)
            raise VaultLockedError("The project vault auto-locked after inactivity")
        self._last_activity = time.monotonic()
        return self._connection

    def save(self) -> None:
        connection = self._require_open()
        connection.commit()
        serialized = connection.serialize()
        passphrase = self._passphrase.decode("utf-8")
        encrypted = encrypt_envelope(serialized, passphrase)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(encrypted)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def close(self, *, save: bool = True) -> None:
        if self._connection is None:
            return
        if save:
            self.save()
        self._connection.close()
        self._connection = None
        for index in range(len(self._passphrase)):
            self._passphrase[index] = 0

    def __enter__(self) -> "ProjectVault":
        self._require_open()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close(save=exc is None)

    @contextmanager
    def mutation(self) -> Iterator[sqlite3.Connection]:
        connection = self._require_open()
        try:
            yield connection
            connection.commit()
            self.save()
        except Exception:
            connection.rollback()
            raise

    def project(self) -> dict[str, Any]:
        row = self._require_open().execute("SELECT * FROM project").fetchone()
        return dict(row)

    def summary(self) -> dict[str, Any]:
        connection = self._require_open()
        project = self.project()
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("source_media", "transcript_version", "segment", "code", "coding", "memo", "analysis_run")
        }
        return {"project": project, "counts": counts, "analyzers": [item.manifest() for item in ANALYZERS.values()]}

    def _audit(
        self,
        connection: sqlite3.Connection,
        event_type: str,
        object_type: str,
        object_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        # Details must contain identifiers and counts only, never transcript text.
        connection.execute(
            """INSERT INTO audit_event
               (occurred_at, event_type, object_type, object_id, details_json)
               VALUES (?, ?, ?, ?, ?)""",
            (utc_now(), event_type, object_type, object_id, json.dumps(details or {}, sort_keys=True)),
        )

    def add_transcript(
        self,
        display_name: str,
        segments: Iterable[ImportedSegment],
        *,
        source_format: str,
        language: str | None = None,
        source_bytes: bytes | None = None,
    ) -> dict[str, str]:
        normalized = list(segments)
        validate_segments(normalized)
        content = json.dumps([item.to_dict() for item in normalized], sort_keys=True).encode("utf-8")
        source_id, transcript_id = new_id("source"), new_id("transcript")
        now = utc_now()
        project_id = self.project()["id"]
        with self.mutation() as connection:
            connection.execute(
                """INSERT INTO source_media
                   (id, project_id, display_name, media_type, original_sha256, created_at)
                   VALUES (?, ?, ?, 'transcript', ?, ?)""",
                (source_id, project_id, display_name, sha256_bytes(source_bytes or content), now),
            )
            connection.execute(
                """INSERT INTO transcript_version
                   (id, source_id, version_number, label, language, source_format,
                    content_sha256, immutable, created_at)
                   VALUES (?, ?, 1, 'Imported original', ?, ?, ?, 1, ?)""",
                (transcript_id, source_id, language, source_format, sha256_bytes(content), now),
            )
            connection.executemany(
                """INSERT INTO segment
                   (id, transcript_id, ordinal, start_ms, end_ms, speaker, text, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        new_id("segment"), transcript_id, ordinal, item.start_ms, item.end_ms,
                        item.speaker, item.text, item.confidence,
                    )
                    for ordinal, item in enumerate(normalized)
                ],
            )
            self._audit(connection, "imported", "transcript", transcript_id, {"segment_count": len(normalized)})
        return {"source_id": source_id, "transcript_id": transcript_id}

    def add_managed_media(
        self,
        source_path: Path | str,
        *,
        media_type: str,
        duration_ms: int | None = None,
    ) -> str:
        source = Path(source_path)
        source_id = new_id("source")
        managed_dir = self.path.with_suffix(self.path.suffix + ".media")
        encrypted_path = managed_dir / f"{source_id}.tsmedia"
        connection = self._require_open()
        media_key = bytes(connection.execute("SELECT value FROM vault_secret WHERE name='media_key'").fetchone()[0])
        metadata = encrypt_managed_file(source, encrypted_path, media_key)
        digest = hashlib.sha256()
        with source.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        project_id = self.project()["id"]
        try:
            with self.mutation() as mutable:
                mutable.execute(
                    """INSERT INTO source_media
                       (id, project_id, display_name, media_type, original_sha256,
                        encrypted_path, duration_ms, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (source_id, project_id, source.name, media_type, digest.hexdigest(), str(encrypted_path), duration_ms, utc_now()),
                )
                self._audit(mutable, "imported", "media", source_id, metadata)
        except Exception:
            encrypted_path.unlink(missing_ok=True)
            raise
        return source_id

    def list_segments(self, transcript_id: str | None = None) -> list[dict[str, Any]]:
        connection = self._require_open()
        query = """SELECT s.*, sm.display_name AS source_name
                   FROM segment s
                   JOIN transcript_version tv ON tv.id=s.transcript_id
                   JOIN source_media sm ON sm.id=tv.source_id"""
        params: tuple[Any, ...] = ()
        if transcript_id:
            query += " WHERE s.transcript_id=?"
            params = (transcript_id,)
        query += " ORDER BY sm.display_name, s.ordinal"
        return [dict(row) for row in connection.execute(query, params)]

    def create_corrected_version(
        self,
        transcript_id: str,
        edits: dict[str, str],
        *,
        label: str = "Researcher corrected",
    ) -> str:
        connection = self._require_open()
        parent = connection.execute("SELECT * FROM transcript_version WHERE id=?", (transcript_id,)).fetchone()
        if not parent:
            raise KeyError(transcript_id)
        source_segments = self.list_segments(transcript_id)
        next_version = connection.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 FROM transcript_version WHERE source_id=?",
            (parent["source_id"],),
        ).fetchone()[0]
        new_transcript_id = new_id("transcript")
        content = [
            {
                "start_ms": item["start_ms"], "end_ms": item["end_ms"],
                "speaker": item["speaker"], "text": edits.get(item["id"], item["text"]),
                "confidence": item["confidence"],
            }
            for item in source_segments
        ]
        digest = sha256_bytes(json.dumps(content, sort_keys=True).encode("utf-8"))
        with self.mutation() as mutable:
            mutable.execute(
                """INSERT INTO transcript_version
                   (id, source_id, version_number, label, language, source_format,
                    content_sha256, immutable, parent_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (
                    new_transcript_id, parent["source_id"], next_version, label,
                    parent["language"], parent["source_format"], digest, transcript_id, utc_now(),
                ),
            )
            mutable.executemany(
                """INSERT INTO segment
                   (id, transcript_id, ordinal, start_ms, end_ms, speaker, text, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (new_id("segment"), new_transcript_id, ordinal, item["start_ms"], item["end_ms"], item["speaker"], item["text"], item["confidence"])
                    for ordinal, item in enumerate(content)
                ],
            )
            self._audit(mutable, "derived", "transcript", new_transcript_id, {"parent_id": transcript_id, "edited_segment_count": len(edits)})
        return new_transcript_id

    def search(self, query: str, *, speaker: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        connection = self._require_open()
        sql = """SELECT s.id, s.transcript_id, s.start_ms, s.end_ms, s.speaker, s.text,
                        sm.display_name AS source_name, bm25(segment_fts) AS lexical_score
                 FROM segment_fts
                 JOIN segment s ON s.rowid=segment_fts.rowid
                 JOIN transcript_version tv ON tv.id=s.transcript_id
                 JOIN source_media sm ON sm.id=tv.source_id
                 WHERE segment_fts MATCH ?"""
        params: list[Any] = [query]
        if speaker:
            sql += " AND s.speaker=?"
            params.append(speaker)
        sql += " ORDER BY lexical_score LIMIT ?"
        params.append(min(max(limit, 1), 500))
        try:
            return [dict(row) for row in connection.execute(sql, params)]
        except sqlite3.OperationalError as exc:
            raise ValueError("Invalid search syntax. Check quotes, parentheses, and Boolean operators.") from exc

    def hybrid_search(self, query: str, *, speaker: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Combine FTS relevance with an exact, in-memory local vector baseline."""
        from .semantic import HashingEmbeddingProvider, exact_similarity

        segments = [item for item in self.list_segments() if not speaker or item.get("speaker") == speaker]
        try:
            lexical = self.search(query, speaker=speaker, limit=max(limit * 3, 100))
        except ValueError:
            lexical = self.search(f'"{query.replace(chr(34), "")}"', speaker=speaker, limit=max(limit * 3, 100))
        lexical_rank = {item["id"]: 1 / (60 + rank) for rank, item in enumerate(lexical, start=1)}
        semantic = exact_similarity(query, segments, HashingEmbeddingProvider())
        semantic_rank = {segment_id: 1 / (60 + rank) for rank, (segment_id, score) in enumerate(semantic, start=1) if score > 0}
        by_id = {item["id"]: item for item in segments}
        ranked = sorted(
            ((segment_id, lexical_rank.get(segment_id, 0) + semantic_rank.get(segment_id, 0)) for segment_id in set(lexical_rank) | set(semantic_rank)),
            key=lambda item: item[1],
            reverse=True,
        )[: min(max(limit, 1), 500)]
        return [by_id[segment_id] | {"hybrid_score": score, "embedding_provider": "sklearn-hashing-word-char"} for segment_id, score in ranked]

    def create_code(
        self,
        name: str,
        description: str = "",
        *,
        parent_id: str | None = None,
        color: str = "#6f7bf7",
    ) -> str:
        code_id = new_id("code")
        with self.mutation() as connection:
            connection.execute(
                "INSERT INTO code VALUES (?, ?, ?, ?, ?, ?, ?)",
                (code_id, self.project()["id"], parent_id, name.strip(), description.strip(), color, utc_now()),
            )
            self._audit(connection, "created", "code", code_id)
        return code_id

    def list_codes(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._require_open().execute("SELECT * FROM code ORDER BY name")]

    def apply_code(self, code_id: str, segment_id: str, *, note: str = "", status: str = "confirmed") -> str:
        coding_id = new_id("coding")
        connection = self._require_open()
        segment = connection.execute("SELECT length(text) AS size FROM segment WHERE id=?", (segment_id,)).fetchone()
        if not segment:
            raise KeyError(segment_id)
        with self.mutation() as mutable:
            mutable.execute(
                """INSERT INTO coding
                   (id, code_id, segment_id, start_char, end_char, note, status, created_at)
                   VALUES (?, ?, ?, 0, ?, ?, ?, ?)""",
                (coding_id, code_id, segment_id, segment["size"], note, status, utc_now()),
            )
            self._audit(mutable, "applied", "coding", coding_id, {"code_id": code_id, "segment_id": segment_id})
        return coding_id

    def create_memo(self, title: str, body: str, *, segment_id: str | None = None) -> str:
        memo_id, now = new_id("memo"), utc_now()
        with self.mutation() as connection:
            connection.execute(
                "INSERT INTO memo VALUES (?, ?, ?, ?, ?, ?, ?)",
                (memo_id, self.project()["id"], segment_id, title, body, now, now),
            )
            self._audit(connection, "created", "memo", memo_id, {"segment_id": segment_id})
        return memo_id

    def run_analyzer(self, analyzer_id: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            analyzer = ANALYZERS[analyzer_id]
        except KeyError as exc:
            raise ValueError(f"Unknown analyzer: {analyzer_id}") from exc
        parameters = parameters or {}
        segments = self.list_segments()
        project_id = self.project()["id"]
        input_hash = analysis_input_hash(segments, parameters)
        run_id, started_at = new_id("analysis"), utc_now()
        context = AnalyzerContext(project_id, input_hash, segments)
        result = analyzer.run(context, parameters)
        completed_at = utc_now()
        with self.mutation() as connection:
            connection.execute(
                """INSERT INTO analysis_run
                   (id, project_id, analyzer_id, analyzer_version, parameters_json,
                    input_hash, status, output_json, started_at, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?)""",
                (
                    run_id, project_id, analyzer.analyzer_id, analyzer.version,
                    json.dumps(parameters, sort_keys=True), input_hash,
                    json.dumps(result, sort_keys=True), started_at, completed_at,
                ),
            )
            self._audit(connection, "completed", "analysis", run_id, {"analyzer_id": analyzer_id})
        return {"run_id": run_id, "manifest": analyzer.manifest(), "input_hash": input_hash, "output": result}

    def detect_redactions(self) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        with self.mutation() as connection:
            for segment in self.list_segments():
                for detected in detect_identifiers(segment["text"]):
                    candidate_id = new_id("redaction")
                    item = detected.to_dict() | {"id": candidate_id, "segment_id": segment["id"], "status": "pending"}
                    candidates.append(item)
                    connection.execute(
                        """INSERT INTO redaction_candidate
                           (id, segment_id, entity_type, original_text, start_char,
                            end_char, confidence, status, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                        (
                            candidate_id, segment["id"], detected.entity_type, detected.text,
                            detected.start_char, detected.end_char, detected.confidence, utc_now(),
                        ),
                    )
            self._audit(connection, "detected", "redaction_batch", new_id("batch"), {"candidate_count": len(candidates)})
        return candidates

    def list_redactions(self) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self._require_open().execute(
                """SELECT rc.*, s.text AS source_text, s.start_ms, s.end_ms
                   FROM redaction_candidate rc JOIN segment s ON s.id=rc.segment_id
                   ORDER BY s.start_ms, rc.start_char"""
            )
        ]

    def review_redaction(self, candidate_id: str, *, status: str, replacement: str | None = None) -> None:
        if status not in {"confirmed", "rejected"}:
            raise ValueError("Redaction status must be confirmed or rejected")
        if status == "confirmed" and not replacement:
            raise ValueError("Confirmed redactions require a replacement")
        with self.mutation() as connection:
            changed = connection.execute(
                "UPDATE redaction_candidate SET status=?, replacement=? WHERE id=?",
                (status, replacement, candidate_id),
            ).rowcount
            if not changed:
                raise KeyError(candidate_id)
            self._audit(connection, "reviewed", "redaction", candidate_id, {"status": status})

    def export_json(self) -> bytes:
        connection = self._require_open()
        tables = ("project", "source_media", "transcript_version", "segment", "code", "coding", "memo", "analysis_run", "redaction_candidate", "audit_event")
        payload = {
            "format": "TranscriptSeek Research Export",
            "version": 1,
            "exported_at": utc_now(),
            "tables": {table: [dict(row) for row in connection.execute(f"SELECT * FROM {table}")] for table in tables},
        }
        return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")

    def export_segments_csv(self) -> bytes:
        output = io.StringIO()
        fields = ["id", "source_name", "transcript_id", "start_ms", "end_ms", "speaker", "text", "confidence"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(self.list_segments())
        return output.getvalue().encode("utf-8")

    def export_srt(self, transcript_id: str, *, redacted: bool = False) -> bytes:
        redactions = self.list_redactions() if redacted else []
        return segments_to_srt(self.list_segments(transcript_id), redactions)

    def export_vtt(self, transcript_id: str, *, redacted: bool = False) -> bytes:
        redactions = self.list_redactions() if redacted else []
        return segments_to_vtt(self.list_segments(transcript_id), redactions)

    def export_refi_codebook(self) -> bytes:
        return export_refi_codebook(self.list_codes())

    def import_refi_codebook(self, payload: bytes) -> list[str]:
        imported = import_refi_codebook(payload)
        ids: list[str] = []
        id_map: dict[str, str] = {}
        for code in imported:
            created = self.create_code(
                code["name"], code["description"],
                parent_id=id_map.get(code["parent_id"]), color=code["color"],
            )
            id_map[code["id"]] = created
            ids.append(created)
        return ids

    def backup(self, destination: Path | str) -> Path:
        self.save()
        target = Path(destination)
        if target.exists():
            raise FileExistsError(target)
        shutil.copyfile(self.path, target)
        return target
