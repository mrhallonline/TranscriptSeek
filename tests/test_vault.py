import json

import pytest

from transcriptseek.crypto import VaultAuthenticationError
from transcriptseek.importers import ImportedSegment
from transcriptseek.vault import ProjectVault, VaultLockedError


SEGMENTS = [
    ImportedSegment(0, 5000, "My email is alex@example.org and I value neighborhood trust.", "Participant 1"),
    ImportedSegment(5000, 10000, "Trust grows through repeated conversations.", "Participant 2"),
    ImportedSegment(10000, 15000, "The neighborhood meeting changed my mind.", "Participant 1"),
]


def test_research_workflow_persists_encrypted(tmp_path) -> None:
    path = tmp_path / "study.tsvault"
    vault = ProjectVault.create(path, "a strong passphrase", name="Synthetic study", irb_protocol="TEST-001")
    imported = vault.add_transcript("interview.srt", SEGMENTS, source_format="srt", language="en")
    results = vault.search('"neighborhood"')
    assert len(results) == 2
    code_id = vault.create_code("Community trust", "Mentions of relational trust")
    vault.apply_code(code_id, results[0]["id"])
    vault.create_memo("Early note", "Synthetic research memo", segment_id=results[0]["id"])
    frequency = vault.run_analyzer("frequency", {"limit": 5})
    assert frequency["manifest"]["deterministic"] is True
    candidates = vault.detect_redactions()
    assert candidates[0]["entity_type"] == "EMAIL"
    vault.review_redaction(candidates[0]["id"], status="confirmed", replacement="[EMAIL_1]")
    redacted_srt = vault.export_srt(imported["transcript_id"], redacted=True)
    assert b"[EMAIL_1]" in redacted_srt and b"alex@example.org" not in redacted_srt
    corrected_id = vault.create_corrected_version(
        imported["transcript_id"], {results[0]["id"]: "A researcher-confirmed correction."}
    )
    assert "A researcher-confirmed correction." in {item["text"] for item in vault.list_segments(corrected_id)}
    hybrid = vault.hybrid_search("community confidence")
    assert hybrid and hybrid[0]["embedding_provider"] == "sklearn-hashing-word-char"
    exported = json.loads(vault.export_json())
    assert exported["tables"]["project"][0]["irb_protocol"] == "TEST-001"
    vault.close()

    raw = path.read_bytes()
    assert b"alex@example.org" not in raw
    assert b"Synthetic study" not in raw
    with pytest.raises(VaultAuthenticationError):
        ProjectVault.open(path, "wrong passphrase")

    reopened = ProjectVault.open(path, "a strong passphrase")
    assert reopened.summary()["counts"]["coding"] == 1
    assert len(reopened.list_redactions()) == 1
    reopened.close()


def test_refi_codebook_round_trip(tmp_path) -> None:
    first = ProjectVault.create(tmp_path / "first.tsvault", "passphrase", name="First")
    parent = first.create_code("Parent", "Top-level code", color="#AABBCC")
    first.create_code("Child", "Nested code", parent_id=parent)
    payload = first.export_refi_codebook()
    assert b"urn:QDA-XML:codebook:1.0" in payload
    assert b'color="#AABBCC"' in payload

    second = ProjectVault.create(tmp_path / "second.tsvault", "passphrase", name="Second")
    second.import_refi_codebook(payload)
    codes = second.list_codes()
    assert [item["name"] for item in codes] == ["Child", "Parent"]
    assert next(item for item in codes if item["name"] == "Child")["parent_id"] is not None
    first.close()
    second.close()


def test_auto_lock(tmp_path) -> None:
    vault = ProjectVault.create(tmp_path / "lock.tsvault", "passphrase", name="Lock test", auto_lock_seconds=1)
    vault._last_activity -= 2
    with pytest.raises(VaultLockedError):
        vault.project()
    assert vault.is_open is False
