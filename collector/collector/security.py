from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken

from collector.config import get_settings


def _build_key(secret: str) -> bytes:
    raw = secret.encode("utf-8")
    padded = (raw * ((32 // max(1, len(raw))) + 2))[:32]
    return base64.urlsafe_b64encode(padded)


def decrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    cipher = Fernet(_build_key(get_settings().password_encryption_key))
    try:
        return cipher.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:  # pragma: no cover - indicates config mismatch
        raise ValueError("Invalid encrypted secret") from exc
