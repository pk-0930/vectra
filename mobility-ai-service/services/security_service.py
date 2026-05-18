import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta

from config.auth_config import get_auth_config


def utc_now() -> datetime:
    return datetime.now(UTC)


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}".encode("utf-8"))


class SecurityService:
    def __init__(self):
        self.config = get_auth_config()

    def hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        iterations = 390000
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            algorithm, raw_iterations, salt, expected_hash = password_hash.split("$", 3)
        except ValueError:
            return False

        if algorithm != "pbkdf2_sha256":
            return False

        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(raw_iterations),
        )
        return hmac.compare_digest(digest.hex(), expected_hash)

    def create_access_token(self, *, user_id: int, email: str) -> str:
        expires_at = utc_now() + timedelta(hours=self.config.token_expiration_hours)
        payload = {
            "sub": user_id,
            "email": email,
            "exp": expires_at.isoformat(),
        }
        payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        signature = hmac.new(
            self.config.token_secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).digest()
        return f"{_b64_encode(payload_bytes)}.{_b64_encode(signature)}"

    def decode_access_token(self, token: str) -> dict | None:
        try:
            encoded_payload, encoded_signature = token.split(".", 1)
            payload_bytes = _b64_decode(encoded_payload)
            expected_signature = hmac.new(
                self.config.token_secret.encode("utf-8"),
                payload_bytes,
                hashlib.sha256,
            ).digest()
            provided_signature = _b64_decode(encoded_signature)
            if not hmac.compare_digest(expected_signature, provided_signature):
                return None

            payload = json.loads(payload_bytes.decode("utf-8"))
            if utc_now() >= datetime.fromisoformat(payload["exp"]):
                return None
            return payload
        except Exception:
            return None
