from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _build_key(secret: str) -> bytes:
    raw = secret.encode("utf-8")
    padded = (raw * ((32 // max(1, len(raw))) + 2))[:32]
    return base64.urlsafe_b64encode(padded)


def encrypt_secret(value: str) -> str:
    cipher = Fernet(_build_key(get_settings().password_encryption_key))
    return cipher.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str | None) -> str | None:
    if value is None:
        return None
    cipher = Fernet(_build_key(get_settings().password_encryption_key))
    try:
        return cipher.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Invalid encrypted secret") from exc


def hash_password(password: str, iterations: int = 390000) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256:{iterations}:{salt}:{base64.urlsafe_b64encode(digest).decode('utf-8')}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        if "$" in password_hash:
            algorithm, iterations_str, salt, encoded_digest = password_hash.split("$", 3)
        else:
            algorithm, iterations_str, salt, encoded_digest = password_hash.split(":", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations_str),
    )
    expected = base64.urlsafe_b64decode(encoded_digest.encode("utf-8"))
    return hmac.compare_digest(digest, expected)
