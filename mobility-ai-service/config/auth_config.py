from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AuthConfig:
    token_secret: str
    token_expiration_hours: int


def get_auth_config() -> AuthConfig:
    secret = os.environ.get("AUTH_TOKEN_SECRET", "")
    if len(secret.strip()) < 32 or secret.strip() == "vectra-dev-secret":
        raise ValueError("AUTH_TOKEN_SECRET must be explicitly configured with at least 32 characters.")
    try:
        expiration = int(os.environ.get("AUTH_TOKEN_EXPIRATION_HOURS", "24"))
    except ValueError as exc:
        raise ValueError("AUTH_TOKEN_EXPIRATION_HOURS must be a positive integer.") from exc
    if expiration <= 0:
        raise ValueError("AUTH_TOKEN_EXPIRATION_HOURS must be a positive integer.")
    return AuthConfig(token_secret=secret, token_expiration_hours=expiration)
