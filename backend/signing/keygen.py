"""Ephemeral Ed25519 demo keypair (proto.demo2 §5.6).

Demo attestation only — NOT a production PKI signature.
"""
from __future__ import annotations

import hashlib
import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

_KEY_DIR = os.path.join(os.path.dirname(__file__), "_keys")
_PRIV = os.path.join(_KEY_DIR, "demo_ed25519.key")


def ensure_key() -> Ed25519PrivateKey:
    os.makedirs(_KEY_DIR, exist_ok=True)
    if os.path.exists(_PRIV):
        with open(_PRIV, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with open(_PRIV, "wb") as f:
        f.write(pem)
    return key


def key_id(key: Ed25519PrivateKey) -> str:
    pub = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return "demo-" + hashlib.sha256(pub).hexdigest()[:16]


def public_pem(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
