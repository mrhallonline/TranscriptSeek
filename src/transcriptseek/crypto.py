"""Authenticated encryption primitives for portable project vaults.

The module deliberately has no network or logging dependencies. Vault metadata uses
Argon2id for passphrase derivation and AES-256-GCM for authenticated encryption.
Managed files are split into independently authenticated chunks to permit seeking.
"""

from __future__ import annotations

import base64
import json
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


MAGIC = b"TSV1"
MEDIA_MAGIC = b"TSM1"
DEFAULT_CHUNK_SIZE = 1024 * 1024
KDF_ITERATIONS = 3
KDF_MEMORY_KIB = 64 * 1024
KDF_LANES = 4


class VaultAuthenticationError(ValueError):
    """Raised when a vault passphrase or authenticated payload is invalid."""


@dataclass(frozen=True)
class KdfParameters:
    salt: bytes
    iterations: int = KDF_ITERATIONS
    memory_kib: int = KDF_MEMORY_KIB
    lanes: int = KDF_LANES

    def derive(self, passphrase: str) -> bytes:
        if not passphrase:
            raise ValueError("A non-empty project passphrase is required")
        return hash_secret_raw(
            secret=passphrase.encode("utf-8"),
            salt=self.salt,
            time_cost=self.iterations,
            memory_cost=self.memory_kib,
            parallelism=self.lanes,
            hash_len=32,
            type=Type.ID,
        )


def new_kdf_parameters() -> KdfParameters:
    return KdfParameters(salt=os.urandom(16))


def encrypt_envelope(plaintext: bytes, passphrase: str, *, aad: bytes = MAGIC) -> bytes:
    params = new_kdf_parameters()
    key = params.derive(passphrase)
    nonce = os.urandom(12)
    header = {
        "salt": base64.b64encode(params.salt).decode("ascii"),
        "iterations": params.iterations,
        "memory_kib": params.memory_kib,
        "lanes": params.lanes,
        "nonce": base64.b64encode(nonce).decode("ascii"),
    }
    encoded_header = json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad + encoded_header)
    return aad + struct.pack(">I", len(encoded_header)) + encoded_header + ciphertext


def decrypt_envelope(payload: bytes, passphrase: str, *, aad: bytes = MAGIC) -> bytes:
    if not payload.startswith(aad) or len(payload) < len(aad) + 4:
        raise VaultAuthenticationError("Not a supported TranscriptSeek encrypted payload")
    header_size = struct.unpack(">I", payload[len(aad) : len(aad) + 4])[0]
    header_start = len(aad) + 4
    header_end = header_start + header_size
    try:
        header_bytes = payload[header_start:header_end]
        header = json.loads(header_bytes)
        params = KdfParameters(
            salt=base64.b64decode(header["salt"]),
            iterations=int(header["iterations"]),
            memory_kib=int(header["memory_kib"]),
            lanes=int(header["lanes"]),
        )
        key = params.derive(passphrase)
        nonce = base64.b64decode(header["nonce"])
        return AESGCM(key).decrypt(nonce, payload[header_end:], aad + header_bytes)
    except (InvalidTag, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise VaultAuthenticationError("Incorrect passphrase or tampered vault") from exc


def encrypt_managed_file(
    source: Path,
    destination: Path,
    key: bytes,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> dict[str, int]:
    """Encrypt a file in seekable, independently authenticated chunks."""
    if len(key) != 32:
        raise ValueError("Managed-file keys must be 32 bytes")
    destination.parent.mkdir(parents=True, exist_ok=True)
    aes = AESGCM(key)
    chunk_count = 0
    size = source.stat().st_size
    with source.open("rb") as incoming, destination.open("wb") as outgoing:
        outgoing.write(MEDIA_MAGIC)
        outgoing.write(struct.pack(">IQ", chunk_size, size))
        while chunk := incoming.read(chunk_size):
            nonce = os.urandom(12)
            aad = MEDIA_MAGIC + struct.pack(">I", chunk_count)
            encrypted = aes.encrypt(nonce, chunk, aad)
            outgoing.write(nonce)
            outgoing.write(struct.pack(">I", len(encrypted)))
            outgoing.write(encrypted)
            chunk_count += 1
    return {"size": size, "chunk_size": chunk_size, "chunk_count": chunk_count}


def iter_decrypted_chunks(source: BinaryIO, key: bytes) -> Iterator[bytes]:
    if source.read(4) != MEDIA_MAGIC:
        raise VaultAuthenticationError("Not an encrypted TranscriptSeek media file")
    source.read(12)  # chunk size and original size are informative for the caller
    aes = AESGCM(key)
    index = 0
    while nonce := source.read(12):
        if len(nonce) != 12:
            raise VaultAuthenticationError("Truncated media nonce")
        length_bytes = source.read(4)
        if len(length_bytes) != 4:
            raise VaultAuthenticationError("Truncated media chunk header")
        length = struct.unpack(">I", length_bytes)[0]
        ciphertext = source.read(length)
        if len(ciphertext) != length:
            raise VaultAuthenticationError("Truncated media chunk")
        try:
            yield aes.decrypt(nonce, ciphertext, MEDIA_MAGIC + struct.pack(">I", index))
        except InvalidTag as exc:
            raise VaultAuthenticationError("Managed media failed authentication") from exc
        index += 1
