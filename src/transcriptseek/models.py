"""Verified offline model packages and local Whisper transcription."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .importers import ImportedSegment


@dataclass(frozen=True)
class ModelManifest:
    model_id: str
    kind: str
    engine: str
    version: str
    files: dict[str, str]
    languages: list[str]
    limitations: str

    @classmethod
    def load(cls, path: Path) -> "ModelManifest":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(**payload)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_package(package: Path | str) -> ModelManifest:
    source = Path(package).resolve()
    manifest = ModelManifest.load(source / "manifest.json")
    if not manifest.files:
        raise ValueError("Model manifest must include at least one checksummed file")
    for relative_name, expected_hash in manifest.files.items():
        target = (source / relative_name).resolve()
        if source not in target.parents or not target.is_file():
            raise ValueError(f"Unsafe or missing model file: {relative_name}")
        if file_sha256(target) != expected_hash.lower():
            raise ValueError(f"Model checksum failed: {relative_name}")
    return manifest


def install_offline_model_package(
    package: Path | str,
    model_root: Path | str,
    *,
    vault_open: bool,
) -> Path:
    if vault_open:
        raise RuntimeError("Lock the project vault before installing or updating models")
    source = Path(package).resolve()
    manifest = verify_model_package(source)
    destination = Path(model_root) / manifest.model_id
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.installing")
    shutil.copytree(source, temporary)
    try:
        verify_model_package(temporary)
        temporary.replace(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


class LocalWhisperTranscriber:
    engine_id = "faster-whisper"

    def __init__(self, model_path: Path | str, *, device: str = "cpu", compute_type: str = "int8") -> None:
        self.model_path = Path(model_path).resolve()
        manifest = verify_model_package(self.model_path)
        if manifest.kind != "transcription" or manifest.engine != self.engine_id:
            raise ValueError("The selected package is not a compatible transcription model")
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("Install TranscriptSeek's transcription dependencies to use local Whisper") from exc
        # A path plus local_files_only prevents the engine from resolving or downloading
        # a remote model identifier.
        self._model = WhisperModel(
            str(self.model_path), device=device, compute_type=compute_type, local_files_only=True
        )
        self.manifest = manifest

    def transcribe(
        self,
        media_path: Path | str,
        *,
        language: str | None = None,
        beam_size: int = 5,
    ) -> tuple[list[ImportedSegment], dict[str, Any]]:
        generated, info = self._model.transcribe(
            str(Path(media_path).resolve()),
            language=language,
            beam_size=beam_size,
            word_timestamps=True,
        )
        segments = [
            ImportedSegment(
                start_ms=round(item.start * 1000),
                end_ms=round(item.end * 1000),
                text=item.text.strip(),
                confidence=None,
            )
            for item in generated
            if item.text.strip()
        ]
        provenance = {
            "engine": self.engine_id,
            "model_id": self.manifest.model_id,
            "model_version": self.manifest.version,
            "language": getattr(info, "language", language),
            "language_probability": getattr(info, "language_probability", None),
            "beam_size": beam_size,
        }
        return segments, provenance

