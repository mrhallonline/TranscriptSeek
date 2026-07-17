import hashlib
import json

import pytest

from transcriptseek.models import install_offline_model_package, verify_model_package


def make_package(path) -> None:
    path.mkdir()
    model = b"synthetic model bytes"
    (path / "model.bin").write_bytes(model)
    (path / "manifest.json").write_text(
        json.dumps(
            {
                "model_id": "synthetic-whisper",
                "kind": "transcription",
                "engine": "faster-whisper",
                "version": "test",
                "files": {"model.bin": hashlib.sha256(model).hexdigest()},
                "languages": ["en"],
                "limitations": "Synthetic fixture only",
            }
        ),
        encoding="utf-8",
    )


def test_verified_offline_model_install_requires_locked_vault(tmp_path) -> None:
    package = tmp_path / "package"
    make_package(package)
    assert verify_model_package(package).model_id == "synthetic-whisper"
    with pytest.raises(RuntimeError):
        install_offline_model_package(package, tmp_path / "models", vault_open=True)
    installed = install_offline_model_package(package, tmp_path / "models", vault_open=False)
    assert verify_model_package(installed).version == "test"


def test_model_tampering_fails(tmp_path) -> None:
    package = tmp_path / "package"
    make_package(package)
    (package / "model.bin").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        verify_model_package(package)
