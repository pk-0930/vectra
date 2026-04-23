from contextlib import contextmanager
from datetime import datetime

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None
    dict_row = None

from config.postgres_config import PostgresConfig


class PostgresJobRepository:
    def __init__(self, config: PostgresConfig):
        self.config = config

    @contextmanager
    def _connect(self):
        if psycopg is None:
            raise RuntimeError(
                "psycopg is not installed. Install backend dependencies before using Postgres."
            )

        connection = psycopg.connect(**self.config.connection_kwargs(), row_factory=dict_row)
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self):
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS jobs (
                        id TEXT PRIMARY KEY,
                        analysis_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        original_filename TEXT NOT NULL,
                        stored_filename TEXT NOT NULL,
                        video_blob_name TEXT NOT NULL,
                        result_json JSONB NULL,
                        error_message TEXT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL,
                        started_at TIMESTAMPTZ NULL,
                        completed_at TIMESTAMPTZ NULL
                    )
                    """
                )
            connection.commit()

    def insert_job(self, payload: dict) -> dict:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO jobs (
                        id,
                        analysis_type,
                        status,
                        original_filename,
                        stored_filename,
                        video_blob_name,
                        result_json,
                        error_message,
                        created_at,
                        updated_at,
                        started_at,
                        completed_at
                    ) VALUES (
                        %(id)s,
                        %(analysis_type)s,
                        %(status)s,
                        %(original_filename)s,
                        %(stored_filename)s,
                        %(video_blob_name)s,
                        %(result_json)s::jsonb,
                        %(error_message)s,
                        %(created_at)s,
                        %(updated_at)s,
                        %(started_at)s,
                        %(completed_at)s
                    )
                    RETURNING *
                    """,
                    payload,
                )
                row = cursor.fetchone()
            connection.commit()
        return row

    def fetch_job(self, job_id: str) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
                return cursor.fetchone()

    def fetch_jobs(self, limit: int) -> list[dict]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM jobs
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return cursor.fetchall()

    def mark_job_running(self, job_id: str, started_at: datetime) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE jobs
                    SET status = 'running',
                        started_at = %s,
                        updated_at = %s
                    WHERE id = %s AND status = 'queued'
                    RETURNING *
                    """,
                    (started_at, started_at, job_id),
                )
                row = cursor.fetchone()
            connection.commit()
        return row

    def update_job_completion(
        self,
        job_id: str,
        *,
        result_json: str | None,
        error_message: str | None,
        status: str,
        updated_at: datetime,
        completed_at: datetime | None,
    ) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE jobs
                    SET status = %s,
                        result_json = %s::jsonb,
                        error_message = %s,
                        updated_at = %s,
                        completed_at = %s
                    WHERE id = %s
                    RETURNING *
                    """,
                    (
                        status,
                        result_json,
                        error_message,
                        updated_at,
                        completed_at,
                        job_id,
                    ),
                )
                row = cursor.fetchone()
            connection.commit()
        return row
