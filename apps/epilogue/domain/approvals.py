from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return sha256_text(token)


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return f"pbkdf2_sha256${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = encoded.split("$", 2)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hash_password(password, salt=bytes.fromhex(salt_hex)).split("$", 2)[2]
        return hmac.compare_digest(candidate, digest_hex)
    except (TypeError, ValueError):
        return False
