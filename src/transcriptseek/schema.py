"""SQLite schema for the encrypted in-memory project database."""

SCHEMA_VERSION = 1

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE project (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    irb_protocol TEXT,
    retention_date TEXT,
    consent_restrictions TEXT,
    export_warning TEXT,
    schema_version INTEGER NOT NULL
);

CREATE TABLE source_media (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    original_sha256 TEXT NOT NULL,
    encrypted_path TEXT,
    duration_ms INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE vault_secret (
    name TEXT PRIMARY KEY,
    value BLOB NOT NULL
);

CREATE TABLE transcript_version (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source_media(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    label TEXT NOT NULL,
    language TEXT,
    source_format TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    immutable INTEGER NOT NULL DEFAULT 1,
    parent_id TEXT REFERENCES transcript_version(id),
    created_at TEXT NOT NULL,
    UNIQUE(source_id, version_number)
);

CREATE TABLE segment (
    id TEXT PRIMARY KEY,
    transcript_id TEXT NOT NULL REFERENCES transcript_version(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    speaker TEXT,
    text TEXT NOT NULL,
    confidence REAL,
    UNIQUE(transcript_id, ordinal),
    CHECK(start_ms >= 0 AND end_ms >= start_ms)
);

CREATE VIRTUAL TABLE segment_fts USING fts5(
    text,
    speaker,
    content='segment',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER segment_ai AFTER INSERT ON segment BEGIN
  INSERT INTO segment_fts(rowid, text, speaker) VALUES (new.rowid, new.text, new.speaker);
END;
CREATE TRIGGER segment_ad AFTER DELETE ON segment BEGIN
  INSERT INTO segment_fts(segment_fts, rowid, text, speaker)
  VALUES('delete', old.rowid, old.text, old.speaker);
END;

CREATE TABLE code (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES code(id),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    color TEXT NOT NULL DEFAULT '#6f7bf7',
    created_at TEXT NOT NULL
);

CREATE TABLE coding (
    id TEXT PRIMARY KEY,
    code_id TEXT NOT NULL REFERENCES code(id) ON DELETE CASCADE,
    segment_id TEXT NOT NULL REFERENCES segment(id) ON DELETE CASCADE,
    start_char INTEGER NOT NULL DEFAULT 0,
    end_char INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'confirmed',
    created_at TEXT NOT NULL,
    CHECK(end_char >= start_char)
);

CREATE TABLE memo (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    segment_id TEXT REFERENCES segment(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE analysis_run (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    analyzer_id TEXT NOT NULL,
    analyzer_version TEXT NOT NULL,
    model_id TEXT,
    model_hash TEXT,
    parameters_json TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    output_json TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE redaction_candidate (
    id TEXT PRIMARY KEY,
    segment_id TEXT NOT NULL REFERENCES segment(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    original_text TEXT NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    replacement TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE audit_event (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    details_json TEXT NOT NULL
);
"""
