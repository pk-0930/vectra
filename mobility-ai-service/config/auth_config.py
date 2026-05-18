from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AuthConfig:
    token_secret: str
    token_expiration_hours: int


def get_auth_config() -> AuthConfig:
    return AuthConfig(
        token_secret=os.environ.get("AUTH_TOKEN_SECRET", "vectra-dev-secret"),
        token_expiration_hours=int(os.environ.get("AUTH_TOKEN_EXPIRATION_HOURS", "24")),
    )
