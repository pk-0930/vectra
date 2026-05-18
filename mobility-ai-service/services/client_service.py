from datetime import UTC, datetime

from config.postgres_config import get_postgres_config
from repositories.platform_repository import PostgresPlatformRepository


def utc_now() -> datetime:
    return datetime.now(UTC)


class ClientService:
    def __init__(self, repository=None):
        self.repository = repository or PostgresPlatformRepository(get_postgres_config())
        self.repository.initialize()

    def list_clients(self, coach_id: int) -> list[dict]:
        return [self._serialize_client(row) for row in self.repository.list_clients(coach_id)]

    def create_client(self, coach_id: int, payload: dict) -> dict:
        timestamp = utc_now()
        row = self.repository.create_client(
            {
                "coach_id": coach_id,
                "first_name": payload["first_name"].strip(),
                "last_name": payload["last_name"].strip(),
                "dob": payload.get("dob"),
                "gender": payload.get("gender"),
                "height_cm": payload.get("height_cm"),
                "weight_kg": payload.get("weight_kg"),
                "is_active": payload.get("is_active", True),
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
        return self._serialize_client(row)

    def get_client(self, client_id: int, coach_id: int) -> dict | None:
        row = self.repository.fetch_client(client_id, coach_id)
        return self._serialize_client(row) if row else None

    def update_client(self, client_id: int, coach_id: int, payload: dict) -> dict | None:
        row = self.repository.update_client(
            client_id,
            coach_id,
            {
                "first_name": payload["first_name"].strip(),
                "last_name": payload["last_name"].strip(),
                "dob": payload.get("dob"),
                "gender": payload.get("gender"),
                "height_cm": payload.get("height_cm"),
                "weight_kg": payload.get("weight_kg"),
                "is_active": payload.get("is_active", True),
                "updated_at": utc_now(),
            },
        )
        return self._serialize_client(row) if row else None

    def add_goal(self, client_id: int, coach_id: int, payload: dict) -> dict:
        client = self.repository.fetch_client(client_id, coach_id)
        if client is None:
            raise ValueError("Client not found.")

        row = self.repository.add_client_goal(
            {
                "client_id": client_id,
                "goal_type": payload["goal_type"],
                "notes": payload.get("notes"),
                "start_date": payload.get("start_date"),
                "end_date": payload.get("end_date"),
                "is_current": True,
                "created_at": utc_now(),
            }
        )
        return {
            "id": row["id"],
            "client_id": row["client_id"],
            "goal_type": row["goal_type"],
            "notes": row["notes"],
            "start_date": row["start_date"].isoformat() if row["start_date"] else None,
            "end_date": row["end_date"].isoformat() if row["end_date"] else None,
            "is_current": row["is_current"],
        }

    def list_progress_photos(self, client_id: int, coach_id: int) -> list[dict]:
        client = self.repository.fetch_client(client_id, coach_id)
        if client is None:
            raise ValueError("Client not found.")

        return [
            {
                "id": row["id"],
                "client_id": row["client_id"],
                "blob_name": row["blob_name"],
                "caption": row["caption"],
                "timeline_type": row["timeline_type"],
                "captured_on": row["captured_on"].isoformat(),
                "created_at": row["created_at"].isoformat(),
            }
            for row in self.repository.list_progress_photos(client_id)
        ]

    def add_progress_photo(self, client_id: int, coach_id: int, payload: dict) -> dict:
        client = self.repository.fetch_client(client_id, coach_id)
        if client is None:
            raise ValueError("Client not found.")

        row = self.repository.add_progress_photo(
            {
                "client_id": client_id,
                "blob_name": payload["blob_name"],
                "caption": payload.get("caption"),
                "timeline_type": payload["timeline_type"],
                "captured_on": payload["captured_on"],
                "created_at": utc_now(),
            }
        )
        return {
            "id": row["id"],
            "client_id": row["client_id"],
            "blob_name": row["blob_name"],
            "caption": row["caption"],
            "timeline_type": row["timeline_type"],
            "captured_on": row["captured_on"].isoformat(),
            "created_at": row["created_at"].isoformat(),
        }

    def _serialize_client(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "coach_id": row["coach_id"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "dob": row["dob"].isoformat() if row["dob"] else None,
            "gender": row["gender"],
            "height_cm": row["height_cm"],
            "weight_kg": row["weight_kg"],
            "is_active": row["is_active"],
            "current_goal_type": row.get("current_goal_type"),
            "current_goal_notes": row.get("current_goal_notes"),
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }
