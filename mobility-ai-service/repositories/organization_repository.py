"""Business-scoped persistence. Callers must authorize the business separately.

An organization ID is a data boundary, not a role grant. Step 2 will bind these
operations to authenticated relationships; never expose this as a generic SQL API.
"""
import json
from contextlib import contextmanager

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from config.postgres_config import PostgresConfig


RECORD_FIELDS = {
    "client_goals": {
        "goal_type", "notes", "start_date", "end_date", "is_current", "created_at",
    },
    "client_progress_photos": {
        "blob_name", "caption", "timeline_type", "captured_on", "created_at",
    },
    "nutrition_plans": {
        "period_type", "period_start", "period_end", "title", "content_json",
        "pdf_blob_name", "created_by_coach_id", "created_at", "updated_at",
    },
    "workout_plans": {
        "period_type", "period_start", "period_end", "title", "content_json",
        "pdf_blob_name", "created_by_coach_id", "created_at", "updated_at",
    },
    "ai_plan_drafts": {
        "coach_id", "plan_kind", "status", "period_type", "period_start", "period_end",
        "title", "content_json", "source_context_json", "generation_preferences_json",
        "coach_prompt", "model_name", "created_at", "updated_at", "approved_plan_id",
    },
    "form_analyses": {
        "analysis_type", "status", "original_filename", "stored_filename",
        "video_blob_name", "result_json", "error_message", "coach_feedback_note",
        "created_at", "updated_at", "started_at", "completed_at",
    },
}
CLIENT_FIELDS = {
    "first_name", "last_name", "dob", "gender", "height_cm", "weight_kg",
    "is_active", "created_at", "updated_at",
}
JSON_FIELDS = {
    "content_json", "source_context_json", "generation_preferences_json", "result_json",
}


class OrganizationRepository:
    def __init__(self, config: PostgresConfig, organization_id: int):
        if type(organization_id) is not int or organization_id <= 0:
            raise ValueError("A positive organization ID is required.")
        self.config = config
        self._organization_id = organization_id

    @property
    def organization_id(self):
        return self._organization_id

    @contextmanager
    def _connect(self):
        with psycopg.connect(**self.config.connection_kwargs(), row_factory=dict_row) as connection:
            yield connection

    def _table(self, record_type):
        if record_type not in RECORD_FIELDS:
            raise ValueError("Unsupported coaching record type.")
        return sql.Identifier(record_type)

    @staticmethod
    def _validate(payload, fields):
        if set(payload) - fields:
            raise ValueError("Unsupported or immutable record fields.")

    @staticmethod
    def _insert(connection, table, payload):
        values = []
        for key, value in payload.items():
            if key in JSON_FIELDS and value is not None:
                value = Jsonb(json.loads(value) if isinstance(value, str) else value)
            values.append(value)
        return connection.execute(sql.SQL(
            "INSERT INTO {} ({}) VALUES ({}) RETURNING *"
        ).format(
            sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, payload)),
            sql.SQL(", ").join(sql.Placeholder() for _ in payload),
        ), values).fetchone()

    def list_clients(self):
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM clients WHERE organization_id=%s ORDER BY id",
                (self.organization_id,),
            ).fetchall()

    def fetch_client(self, client_id):
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM clients WHERE organization_id=%s AND id=%s",
                (self.organization_id, client_id),
            ).fetchone()

    def create_client(self, *, coach_id, payload):
        self._validate(payload, CLIENT_FIELDS)
        with self._connect() as connection:
            return self._insert(connection, "clients", {
                **payload, "coach_id": coach_id, "organization_id": self.organization_id,
            })

    def update_client(self, client_id, payload):
        self._validate(payload, CLIENT_FIELDS - {"created_at"})
        return self._update("clients", client_id, payload)

    def list_records(self, record_type, *, client_id):
        table = self._table(record_type)
        with self._connect() as connection:
            return connection.execute(sql.SQL(
                "SELECT r.* FROM {} r JOIN clients c "
                "ON c.id=r.client_id AND c.organization_id=r.organization_id "
                "WHERE r.organization_id=%s AND r.client_id=%s ORDER BY r.id"
            ).format(table), (self.organization_id, client_id)).fetchall()

    def fetch_record(self, record_type, record_id):
        table = self._table(record_type)
        with self._connect() as connection:
            return connection.execute(sql.SQL(
                "SELECT r.* FROM {} r JOIN clients c "
                "ON c.id=r.client_id AND c.organization_id=r.organization_id "
                "WHERE r.organization_id=%s AND r.id=%s"
            ).format(table), (self.organization_id, record_id)).fetchone()

    def create_record(self, record_type, *, client_id, payload):
        self._table(record_type)
        fields = RECORD_FIELDS[record_type]
        if record_type == "form_analyses":
            fields = fields | {"id"}
        self._validate(payload, fields)
        with self._connect() as connection:
            # Same transaction and row lock as the insert; no check/write race.
            client = connection.execute(
                "SELECT id FROM clients WHERE id=%s AND organization_id=%s FOR UPDATE",
                (client_id, self.organization_id),
            ).fetchone()
            if client is None:
                raise ValueError("Client not found in this organization.")
            if record_type == "client_goals" and payload.get("is_current", True):
                connection.execute(
                    "UPDATE client_goals SET is_current=false "
                    "WHERE organization_id=%s AND client_id=%s",
                    (self.organization_id, client_id),
                )
            return self._insert(connection, record_type, {
                **payload, "client_id": client_id, "organization_id": self.organization_id,
            })

    def update_record(self, record_type, record_id, payload):
        self._table(record_type)
        self._validate(payload, RECORD_FIELDS[record_type] - {
            "created_at", "created_by_coach_id", "coach_id", "plan_kind", "analysis_type",
            "video_blob_name", "stored_filename", "original_filename",
        })
        return self._update(record_type, record_id, payload)

    def _update(self, table, record_id, payload):
        if not payload:
            raise ValueError("At least one update field is required.")
        values = []
        for key, value in payload.items():
            if key in JSON_FIELDS and value is not None:
                value = Jsonb(json.loads(value) if isinstance(value, str) else value)
            values.append(value)
        with self._connect() as connection:
            return connection.execute(sql.SQL(
                "UPDATE {} SET {} WHERE organization_id=%s AND id=%s RETURNING *"
            ).format(
                sql.Identifier(table), sql.SQL(", ").join(
                    sql.SQL("{}=%s").format(sql.Identifier(key)) for key in payload
                ),
            ), [*values, self.organization_id, record_id]).fetchone()

    def claim_analysis(self, analysis_id, timestamp):
        with self._connect() as connection:
            return connection.execute(
                "UPDATE form_analyses SET status='running', started_at=%s, updated_at=%s "
                "WHERE organization_id=%s AND id=%s AND status='queued' RETURNING *",
                (timestamp, timestamp, self.organization_id, analysis_id),
            ).fetchone()

    def resolve_photo(self, blob_name):
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM client_progress_photos WHERE organization_id=%s AND blob_name=%s",
                (self.organization_id, blob_name),
            ).fetchone()
