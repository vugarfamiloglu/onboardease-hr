"""Envelope encryption for documents at rest.

Mirrors the AWS KMS pattern: every file is encrypted with a fresh random data
key (AES-256-GCM); that data key is then *wrapped* (encrypted) with a master
key. Locally the master key lives in data/.master-key (auto-generated, mode
0600); in production the wrapping is delegated to AWS KMS (see storage.py).
"""
import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_MAGIC = b"OEH1"


def _load_master_key(data_dir: Path, env_key: str | None) -> bytes:
    if env_key:
        raw = base64.b64decode(env_key)
        if len(raw) != 32:
            raise ValueError("MASTER_KEY must be base64 of 32 bytes")
        return raw
    key_file = data_dir / ".master-key"
    if key_file.exists():
        return base64.b64decode(key_file.read_text().strip())
    key = AESGCM.generate_key(bit_length=256)
    key_file.write_text(base64.b64encode(key).decode())
    try:
        os.chmod(key_file, 0o600)
    except OSError:
        pass
    return key


class Envelope:
    """Local envelope-encryption provider (the default 'auto encrypt' backend)."""

    def __init__(self, data_dir: Path, env_key: str | None = None):
        self._master = _load_master_key(data_dir, env_key)

    def encrypt(self, plaintext: bytes) -> bytes:
        data_key = AESGCM.generate_key(bit_length=256)
        data_nonce = os.urandom(12)
        ciphertext = AESGCM(data_key).encrypt(data_nonce, plaintext, None)

        wrap_nonce = os.urandom(12)
        wrapped = AESGCM(self._master).encrypt(wrap_nonce, data_key, None)  # 48 bytes

        return _MAGIC + wrap_nonce + wrapped + data_nonce + ciphertext

    def decrypt(self, blob: bytes) -> bytes:
        if blob[:4] != _MAGIC:
            raise ValueError("Not an OnboardEase encrypted blob")
        body = blob[4:]
        wrap_nonce, wrapped, rest = body[:12], body[12:60], body[60:]
        data_key = AESGCM(self._master).decrypt(wrap_nonce, wrapped, None)
        data_nonce, ciphertext = rest[:12], rest[12:]
        return AESGCM(data_key).decrypt(data_nonce, ciphertext, None)
