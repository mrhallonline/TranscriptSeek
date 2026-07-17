import pytest

from transcriptseek.crypto import (
    VaultAuthenticationError,
    decrypt_envelope,
    encrypt_envelope,
    encrypt_managed_file,
    iter_decrypted_chunks,
)


def test_envelope_round_trip_and_wrong_passphrase() -> None:
    encrypted = encrypt_envelope(b"sensitive transcript", "correct horse battery staple")
    assert b"sensitive transcript" not in encrypted
    assert decrypt_envelope(encrypted, "correct horse battery staple") == b"sensitive transcript"
    with pytest.raises(VaultAuthenticationError):
        decrypt_envelope(encrypted, "wrong")


def test_tamper_detection() -> None:
    encrypted = bytearray(encrypt_envelope(b"payload", "passphrase"))
    encrypted[-1] ^= 1
    with pytest.raises(VaultAuthenticationError):
        decrypt_envelope(bytes(encrypted), "passphrase")


def test_chunked_managed_file_round_trip(tmp_path) -> None:
    original = (b"audio-like-data" * 1000) + b"tail"
    source = tmp_path / "sample.wav"
    destination = tmp_path / "sample.tsmedia"
    source.write_bytes(original)
    encrypt_managed_file(source, destination, b"k" * 32, chunk_size=257)
    assert original not in destination.read_bytes()
    with destination.open("rb") as stream:
        assert b"".join(iter_decrypted_chunks(stream, b"k" * 32)) == original
