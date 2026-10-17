"""Crypto helper for AJCloud authentication using standard NaCl Box."""
from __future__ import annotations

import base64
import os
from nacl.public import Box, PrivateKey, PublicKey


def generate_nonce() -> bytes:
    """Generate 24-byte random nonce."""
    return os.urandom(24)


def encrypt_password_challenge(
    password: str,
    client_secret_b64: str,
    server_pub_b64: str,
    nonce: bytes | None = None,
) -> tuple[str, str]:
    """Encrypt password for AJCloud /v1/signin request using standard NaCl Box.

    Returns: (encrypted_password_base64, nonce_base64).
    """
    if nonce is None:
        nonce = generate_nonce()

    client_sec = base64.b64decode(client_secret_b64)
    server_pub = base64.b64decode(server_pub_b64)

    priv = PrivateKey(client_sec)
    pub = PublicKey(server_pub)
    box = Box(priv, pub)

    # box.encrypt(msg, nonce) returns nonce + ciphertext (16 bytes MAC + encrypted msg)
    encrypted = box.encrypt(password.encode("utf-8"), nonce)[len(nonce):]

    # Strip leading zero bytes (as done by nbg.s in the APK)
    idx = 0
    while idx < len(encrypted) and encrypted[idx] == 0:
        idx += 1
    stripped = bytes(encrypted[idx:])

    enc_password = base64.b64encode(stripped).decode("utf-8")
    nonce_b64 = base64.b64encode(nonce).decode("utf-8")
    return enc_password, nonce_b64
