import json
from datetime import UTC, datetime
from typing import Any

from config.postgres_config import get_postgres_config
from repositories.job_repository import PostgresJobRepository


def utc_now() -> datetime:
    return datetime.now(UTC)


class JobStore:
    def __init__(self, repository=None):
        self.repository = repository or PostgresJobRepository(get_postgres_config())
        self.repository.initialize()

    def create_job(
        self,
        *,
        job_id: str,
        analysis_type: str,
        original_filename: str,
        stored_filename: str,
        video_blob_name: str,
    ) -> dict[str, Any]:
        timestamp = utc_now()
        row = self.repository.insert_job(
            {
                "id": job_id,
                "analysis_type": analysis_type,
                "status": "queued",
                "original_filename": original_filename,
                "stored_filename": stored_filename,
                "video_blob_name": video_blob_name,
                "result_json": None,
                "error_message": None,
                "created_at": timestamp,
                "updated_at": timestamp,
                "started_at": None,
                "completed_at": None,
            }
        )
        return self._row_to_job(row)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        row = self.repository.fetch_job(job_id)
        if row is None:
            return None
        return self._row_to_job(row)

    def list_jobs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        return [self._row_to_job(row) for row in self.repository.fetch_jobs(limit)]

    def mark_job_running(self, job_id: str) -> dict[str, Any] | None:
        row = self.repository.mark_job_running(job_id, utc_now())
        if row is None:
            return None
        return self._row_to_job(row)

    def mark_job_completed(self, job_id: str, result: dict[str, Any]) -> dict[str, Any] | None:
        now = utc_now()
        row = self.repository.update_job_completion(
            job_id,
            result_json=json.dumps(result),
            error_message=None,
            status="completed",
            updated_at=now,
            completed_at=now,
        )
        return self._row_to_job(row) if row else None

    def mark_job_failed(self, job_id: str, error_message: str) -> dict[str, Any] | None:
        now = utc_now()
        row = self.repository.update_job_completion(
            job_id,
            result_json=None,
            error_message=error_message,
            status="failed",
            updated_at=now,
            completed_at=now,
        )
        return self._row_to_job(row) if row else None

    def _row_to_job(self, row: dict[str, Any]) -> dict[str, Any]:
        result_json = row["result_json"]
        if isinstance(result_json, str):
            result_payload = json.loads(result_json)
        else:
            result_payload = result_json

        return {
            "id": row["id"],
            "analysis_type": row["analysis_type"],
            "status": row["status"],
            "original_filename": row["original_filename"],
            "stored_filename": row["stored_filename"],
            "video_blob_name": row["video_blob_name"],
            "result": result_payload,
            "error_message": row["error_message"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        }
