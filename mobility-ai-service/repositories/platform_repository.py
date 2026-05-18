from contextlib import contextmanager
from datetime import datetime

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None
    dict_row = None

from config.postgres_config import PostgresConfig


class PostgresPlatformRepository:
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
                    CREATE TABLE IF NOT EXISTS users (
                        id BIGSERIAL PRIMARY KEY,
                        email TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS coaches (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                        first_name TEXT NOT NULL,
                        last_name TEXT NOT NULL,
                        dob DATE NULL,
                        gender TEXT NULL,
                        mobile TEXT NULL,
                        years_of_experience INT NOT NULL DEFAULT 0,
                        associated_gym TEXT NULL,
                        clients_trained INT NOT NULL DEFAULT 0,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS clients (
                        id BIGSERIAL PRIMARY KEY,
                        coach_id BIGINT NOT NULL REFERENCES coaches(id) ON DELETE CASCADE,
                        first_name TEXT NOT NULL,
                        last_name TEXT NOT NULL,
                        dob DATE NULL,
                        gender TEXT NULL,
                        height_cm INT NULL,
                        weight_kg INT NULL,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS client_goals (
                        id BIGSERIAL PRIMARY KEY,
                        client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                        goal_type TEXT NOT NULL,
                        notes TEXT NULL,
                        start_date DATE NULL,
                        end_date DATE NULL,
                        is_current BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS client_progress_photos (
                        id BIGSERIAL PRIMARY KEY,
                        client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                        blob_name TEXT NOT NULL,
                        caption TEXT NULL,
                        timeline_type TEXT NOT NULL,
                        captured_on DATE NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS nutrition_plans (
                        id BIGSERIAL PRIMARY KEY,
                        client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                        period_type TEXT NOT NULL,
                        period_start DATE NOT NULL,
                        period_end DATE NOT NULL,
                        title TEXT NOT NULL,
                        content_json JSONB NOT NULL,
                        pdf_blob_name TEXT NULL,
                        created_by_coach_id BIGINT NOT NULL REFERENCES coaches(id) ON DELETE CASCADE,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workout_plans (
                        id BIGSERIAL PRIMARY KEY,
                        client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                        period_type TEXT NOT NULL,
                        period_start DATE NOT NULL,
                        period_end DATE NOT NULL,
                        title TEXT NOT NULL,
                        content_json JSONB NOT NULL,
                        pdf_blob_name TEXT NULL,
                        created_by_coach_id BIGINT NOT NULL REFERENCES coaches(id) ON DELETE CASCADE,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS form_analyses (
                        id TEXT PRIMARY KEY,
                        client_id BIGINT NULL REFERENCES clients(id) ON DELETE SET NULL,
                        analysis_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        original_filename TEXT NOT NULL,
                        stored_filename TEXT NOT NULL,
                        video_blob_name TEXT NOT NULL,
                        result_json JSONB NULL,
                        error_message TEXT NULL,
                        coach_feedback_note TEXT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL,
                        started_at TIMESTAMPTZ NULL,
                        completed_at TIMESTAMPTZ NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1
                            FROM information_schema.tables
                            WHERE table_name = 'jobs'
                        ) THEN
                            INSERT INTO form_analyses (
                                id,
                                client_id,
                                analysis_type,
                                status,
                                original_filename,
                                stored_filename,
                                video_blob_name,
                                result_json,
                                error_message,
                                coach_feedback_note,
                                created_at,
                                updated_at,
                                started_at,
                                completed_at
                            )
                            SELECT
                                id,
                                NULL,
                                analysis_type,
                                status,
                                original_filename,
                                stored_filename,
                                video_blob_name,
                                result_json,
                                error_message,
                                NULL,
                                created_at,
                                updated_at,
                                started_at,
                                completed_at
                            FROM jobs
                            ON CONFLICT (id) DO NOTHING;
                        END IF;
                    END $$;
                    """
                )
            connection.commit()

    def create_user(self, payload: dict) -> dict:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (email, password_hash, created_at, updated_at)
                    VALUES (%(email)s, %(password_hash)s, %(created_at)s, %(updated_at)s)
                    RETURNING *
                    """,
                    payload,
                )
                row = cursor.fetchone()
            connection.commit()
        return row

    def fetch_user_by_email(self, email: str) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                return cursor.fetchone()

    def fetch_user_by_id(self, user_id: int) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                return cursor.fetchone()

    def create_coach(self, payload: dict) -> dict:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO coaches (
                        user_id,
                        first_name,
                        last_name,
                        dob,
                        gender,
                        mobile,
                        years_of_experience,
                        associated_gym,
                        clients_trained,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        %(user_id)s,
                        %(first_name)s,
                        %(last_name)s,
                        %(dob)s,
                        %(gender)s,
                        %(mobile)s,
                        %(years_of_experience)s,
                        %(associated_gym)s,
                        %(clients_trained)s,
                        %(created_at)s,
                        %(updated_at)s
                    )
                    RETURNING *
                    """,
                    payload,
                )
                row = cursor.fetchone()
            connection.commit()
        return row

    def fetch_coach_by_user_id(self, user_id: int) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM coaches WHERE user_id = %s", (user_id,))
                return cursor.fetchone()

    def list_clients(self, coach_id: int) -> list[dict]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        c.*,
                        goal.goal_type AS current_goal_type,
                        goal.notes AS current_goal_notes
                    FROM clients c
                    LEFT JOIN LATERAL (
                        SELECT goal_type, notes
                        FROM client_goals
                        WHERE client_id = c.id AND is_current = TRUE
                        ORDER BY created_at DESC
                        LIMIT 1
                    ) goal ON TRUE
                    WHERE c.coach_id = %s
                    ORDER BY c.created_at DESC
                    """,
                    (coach_id,),
                )
                return cursor.fetchall()

    def create_client(self, payload: dict) -> dict:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO clients (
                        coach_id,
                        first_name,
                        last_name,
                        dob,
                        gender,
                        height_cm,
                        weight_kg,
                        is_active,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        %(coach_id)s,
                        %(first_name)s,
                        %(last_name)s,
                        %(dob)s,
                        %(gender)s,
                        %(height_cm)s,
                        %(weight_kg)s,
                        %(is_active)s,
                        %(created_at)s,
                        %(updated_at)s
                    )
                    RETURNING *
                    """,
                    payload,
                )
                row = cursor.fetchone()
            connection.commit()
        return row

    def fetch_client(self, client_id: int, coach_id: int) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        c.*,
                        goal.goal_type AS current_goal_type,
                        goal.notes AS current_goal_notes
                    FROM clients c
                    LEFT JOIN LATERAL (
                        SELECT goal_type, notes
                        FROM client_goals
                        WHERE client_id = c.id AND is_current = TRUE
                        ORDER BY created_at DESC
                        LIMIT 1
                    ) goal ON TRUE
                    WHERE c.id = %s AND c.coach_id = %s
                    """,
                    (client_id, coach_id),
                )
                return cursor.fetchone()

    def update_client(self, client_id: int, coach_id: int, payload: dict) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE clients
                    SET first_name = %(first_name)s,
                        last_name = %(last_name)s,
                        dob = %(dob)s,
                        gender = %(gender)s,
                        height_cm = %(height_cm)s,
                        weight_kg = %(weight_kg)s,
                        is_active = %(is_active)s,
                        updated_at = %(updated_at)s
                    WHERE id = %(id)s AND coach_id = %(coach_id)s
                    RETURNING *
                    """,
                    {
                        **payload,
                        "id": client_id,
                        "coach_id": coach_id,
                    },
                )
                row = cursor.fetchone()
            connection.commit()
        return row

    def add_client_goal(self, payload: dict) -> dict:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE client_goals
                    SET is_current = FALSE
                    WHERE client_id = %(client_id)s
                    """,
                    {"client_id": payload["client_id"]},
                )
                cursor.execute(
                    """
                    INSERT INTO client_goals (
                        client_id,
                        goal_type,
                        notes,
                        start_date,
                        end_date,
                        is_current,
                        created_at
                    )
                    VALUES (
                        %(client_id)s,
                        %(goal_type)s,
                        %(notes)s,
                        %(start_date)s,
                        %(end_date)s,
                        %(is_current)s,
                        %(created_at)s
                    )
                    RETURNING *
                    """,
                    payload,
                )
                row = cursor.fetchone()
            connection.commit()
        return row

    def add_progress_photo(self, payload: dict) -> dict:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO client_progress_photos (
                        client_id,
                        blob_name,
                        caption,
                        timeline_type,
                        captured_on,
                        created_at
                    )
                    VALUES (
                        %(client_id)s,
                        %(blob_name)s,
                        %(caption)s,
                        %(timeline_type)s,
                        %(captured_on)s,
                        %(created_at)s
                    )
                    RETURNING *
                    """,
                    payload,
                )
                row = cursor.fetchone()
            connection.commit()
        return row

    def list_progress_photos(self, client_id: int) -> list[dict]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM client_progress_photos
                    WHERE client_id = %s
                    ORDER BY captured_on DESC, created_at DESC
                    """,
                    (client_id,),
                )
                return cursor.fetchall()

    def create_plan(self, table_name: str, payload: dict) -> dict:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {table_name} (
                        client_id,
                        period_type,
                        period_start,
                        period_end,
                        title,
                        content_json,
                        pdf_blob_name,
                        created_by_coach_id,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        %(client_id)s,
                        %(period_type)s,
                        %(period_start)s,
                        %(period_end)s,
                        %(title)s,
                        %(content_json)s::jsonb,
                        %(pdf_blob_name)s,
                        %(created_by_coach_id)s,
                        %(created_at)s,
                        %(updated_at)s
                    )
                    RETURNING *
                    """,
                    payload,
                )
                row = cursor.fetchone()
            connection.commit()
        return row

    def fetch_plan(self, table_name: str, plan_id: int, coach_id: int) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT p.*
                    FROM {table_name} p
                    JOIN clients c ON c.id = p.client_id
                    WHERE p.id = %s AND c.coach_id = %s
                    """,
                    (plan_id, coach_id),
                )
                return cursor.fetchone()

    def list_plans(self, table_name: str, client_id: int, coach_id: int) -> list[dict]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT p.*
                    FROM {table_name} p
                    JOIN clients c ON c.id = p.client_id
                    WHERE p.client_id = %s AND c.coach_id = %s
                    ORDER BY p.period_start DESC, p.created_at DESC
                    """,
                    (client_id, coach_id),
                )
                return cursor.fetchall()

    def update_plan_pdf_blob_name(self, table_name: str, plan_id: int, pdf_blob_name: str) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE {table_name}
                    SET pdf_blob_name = %s
                    WHERE id = %s
                    RETURNING *
                    """,
                    (pdf_blob_name, plan_id),
                )
                row = cursor.fetchone()
            connection.commit()
        return row

    def insert_form_analysis(self, payload: dict) -> dict:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO form_analyses (
                        id,
                        client_id,
                        analysis_type,
                        status,
                        original_filename,
                        stored_filename,
                        video_blob_name,
                        result_json,
                        error_message,
                        coach_feedback_note,
                        created_at,
                        updated_at,
                        started_at,
                        completed_at
                    )
                    VALUES (
                        %(id)s,
                        %(client_id)s,
                        %(analysis_type)s,
                        %(status)s,
                        %(original_filename)s,
                        %(stored_filename)s,
                        %(video_blob_name)s,
                        %(result_json)s::jsonb,
                        %(error_message)s,
                        %(coach_feedback_note)s,
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

    def fetch_form_analysis(self, analysis_id: str) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM form_analyses WHERE id = %s", (analysis_id,))
                return cursor.fetchone()

    def fetch_form_analysis_for_coach(self, analysis_id: str, coach_id: int) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT fa.*
                    FROM form_analyses fa
                    LEFT JOIN clients c ON c.id = fa.client_id
                    WHERE fa.id = %s AND (fa.client_id IS NULL OR c.coach_id = %s)
                    """,
                    (analysis_id, coach_id),
                )
                return cursor.fetchone()

    def fetch_form_analyses(self, coach_id: int, limit: int, client_id: int | None = None) -> list[dict]:
        query = """
            SELECT fa.*
            FROM form_analyses fa
            LEFT JOIN clients c ON c.id = fa.client_id
            WHERE fa.client_id IS NULL OR c.coach_id = %(coach_id)s
        """
        params: dict[str, int] = {"coach_id": coach_id, "limit": limit}
        if client_id is not None:
            query += " AND fa.client_id = %(client_id)s"
            params["client_id"] = client_id
        query += " ORDER BY fa.created_at DESC LIMIT %(limit)s"

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()

    def mark_form_analysis_running(self, analysis_id: str, started_at: datetime) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE form_analyses
                    SET status = 'running',
                        started_at = %s,
                        updated_at = %s
                    WHERE id = %s AND status = 'queued'
                    RETURNING *
                    """,
                    (started_at, started_at, analysis_id),
                )
                row = cursor.fetchone()
            connection.commit()
        return row

    def mark_form_analysis_queued_for_retry(
        self,
        analysis_id: str,
        *,
        error_message: str,
        updated_at: datetime,
    ) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE form_analyses
                    SET status = 'queued',
                        result_json = NULL,
                        error_message = %s,
                        updated_at = %s,
                        started_at = NULL,
                        completed_at = NULL
                    WHERE id = %s AND status = 'running'
                    RETURNING *
                    """,
                    (error_message, updated_at, analysis_id),
                )
                row = cursor.fetchone()
            connection.commit()
        return row

    def update_form_analysis_completion(
        self,
        analysis_id: str,
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
                    UPDATE form_analyses
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
                        analysis_id,
                    ),
                )
                row = cursor.fetchone()
            connection.commit()
        return row

    def update_form_analysis_feedback(self, analysis_id: str, feedback_note: str, updated_at: datetime) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE form_analyses
                    SET coach_feedback_note = %s,
                        updated_at = %s
                    WHERE id = %s
                    RETURNING *
                    """,
                    (feedback_note, updated_at, analysis_id),
                )
                row = cursor.fetchone()
            connection.commit()
        return row
