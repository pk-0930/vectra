import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PostgresConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str
    sslmode: str

    def connection_kwargs(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": self.password,
            "sslmode": self.sslmode,
        }


def get_postgres_config() -> PostgresConfig:
    host = os.environ.get("POSTGRES_HOST")
    dbname = os.environ.get("POSTGRES_DB")
    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")

    missing_keys = [
        key
        for key, value in (
            ("POSTGRES_HOST", host),
            ("POSTGRES_DB", dbname),
            ("POSTGRES_USER", user),
            ("POSTGRES_PASSWORD", password),
        )
        if not value
    ]
    if missing_keys:
        raise RuntimeError(
            "Missing Postgres configuration: "
            + ", ".join(missing_keys)
        )

    return PostgresConfig(
        host=host,
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=dbname,
        user=user,
        password=password,
        sslmode=os.environ.get("POSTGRES_SSLMODE", "require"),
    )
