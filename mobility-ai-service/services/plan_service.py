import json
from datetime import UTC, datetime

from config.postgres_config import get_postgres_config
from repositories.platform_repository import PostgresPlatformRepository


def utc_now() -> datetime:
    return datetime.now(UTC)


class PlanService:
    TABLES = {
        "nutrition": "nutrition_plans",
        "workout": "workout_plans",
    }

    def __init__(self, repository=None):
        self.repository = repository or PostgresPlatformRepository(get_postgres_config())
        self.repository.initialize()

    def create_plan(self, plan_kind: str, coach_id: int, client_id: int, payload: dict) -> dict:
        client = self.repository.fetch_client(client_id, coach_id)
        if client is None:
            raise ValueError("Client not found.")
        table_name = self.TABLES[plan_kind]
        timestamp = utc_now()
        row = self.repository.create_plan(
            table_name,
            {
                "client_id": client_id,
                "period_type": payload["period_type"],
                "period_start": payload["period_start"],
                "period_end": payload["period_end"],
                "title": payload["title"].strip(),
                "content_json": json.dumps(payload["content"]),
                "pdf_blob_name": None,
                "created_by_coach_id": coach_id,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        )
        return self._serialize_plan(row)

    def list_plans(self, plan_kind: str, coach_id: int, client_id: int) -> list[dict]:
        client = self.repository.fetch_client(client_id, coach_id)
        if client is None:
            raise ValueError("Client not found.")
        table_name = self.TABLES[plan_kind]
        return [
            self._serialize_plan(row)
            for row in self.repository.list_plans(table_name, client_id, coach_id)
        ]

    def get_plan(self, plan_kind: str, coach_id: int, plan_id: int) -> dict | None:
        table_name = self.TABLES[plan_kind]
        row = self.repository.fetch_plan(table_name, plan_id, coach_id)
        return self._serialize_plan(row) if row else None

    def set_pdf_blob_name(self, plan_kind: str, plan_id: int, pdf_blob_name: str) -> dict | None:
        table_name = self.TABLES[plan_kind]
        row = self.repository.update_plan_pdf_blob_name(table_name, plan_id, pdf_blob_name)
        return self._serialize_plan(row) if row else None

    def _serialize_plan(self, row: dict) -> dict:
        content_json = row["content_json"]
        if isinstance(content_json, str):
            content = json.loads(content_json)
        else:
            content = content_json

        return {
            "id": row["id"],
            "client_id": row["client_id"],
            "period_type": row["period_type"],
            "period_start": row["period_start"].isoformat(),
            "period_end": row["period_end"].isoformat(),
            "title": row["title"],
            "content": content,
            "pdf_blob_name": row["pdf_blob_name"],
            "created_by_coach_id": row["created_by_coach_id"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }
