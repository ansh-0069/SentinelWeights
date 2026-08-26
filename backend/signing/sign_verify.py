"""Sign / verify a canonical report hash with the Ed25519 demo key."""
from __future__ import annotations

import base64
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from signing.keygen import ensure_key, key_id, public_pem


def canonical_hash(report: dict) -> str:
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def sign_report(report: dict) -> dict:
    key = ensure_key()
    digest = canonical_hash(report)
    sig = key.sign(digest.encode())
    return {
        "algo": "Ed25519",
        "key_id": key_id(key),
        "report_sha256": digest,
        "signature_b64": base64.b64encode(sig).decode(),
        "public_key_pem": public_pem(key),
        "disclaimer": "Demo attestation — locally signed, not a production PKI signature.",
    }


def verify(report_sha256: str, signature_b64: str, public_key_pem: str) -> dict:
    try:
        pub = serialization.load_pem_public_key(public_key_pem.encode())
        assert isinstance(pub, Ed25519PublicKey)
        pub.verify(base64.b64decode(signature_b64), report_sha256.encode())
        return {"valid": True, "message": "Signature valid — report integrity confirmed."}
    except (InvalidSignature, Exception) as e:
        return {"valid": False, "message": f"Signature INVALID: {type(e).__name__}"}
