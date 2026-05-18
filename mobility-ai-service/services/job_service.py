import json
from datetime import UTC, datetime
from typing import Any

from config.postgres_config import get_postgres_config
from repositories.platform_repository import PostgresPlatformRepository


def utc_now() -> datetime:
    return datetime.now(UTC)


class JobService:
    def __init__(self, repository=None):
        self.repository = repository or PostgresPlatformRepository(get_postgres_config())
        self.repository.initialize()

    def create_job(
        self,
        *,
        job_id: str,
        analysis_type: str,
        original_filename: str,
        stored_filename: str,
        video_blob_name: str,
        client_id: int | None = None,
    ) -> dict[str, Any]:
        timestamp = utc_now()
        payload = {
            "id": job_id,
            "client_id": client_id,
            "analysis_type": analysis_type,
            "status": "queued",
            "original_filename": original_filename,
            "stored_filename": stored_filename,
            "video_blob_name": video_blob_name,
            "result_json": None,
            "error_message": None,
            "coach_feedback_note": None,
            "created_at": timestamp,
            "updated_at": timestamp,
            "started_at": None,
            "completed_at": None,
        }
        if hasattr(self.repository, "insert_form_analysis"):
            row = self.repository.insert_form_analysis(payload)
        else:
            legacy_payload = dict(payload)
            legacy_payload.pop("client_id", None)
            legacy_payload.pop("coach_feedback_note", None)
            row = self.repository.insert_job(legacy_payload)
        return self._row_to_job(row)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        if hasattr(self.repository, "fetch_form_analysis"):
            row = self.repository.fetch_form_analysis(job_id)
        else:
            row = self.repository.fetch_job(job_id)
        if row is None:
            return None
        return self._row_to_job(row)

    def list_jobs(
        self,
        *,
        limit: int = 20,
        coach_id: int | None = None,
        client_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if hasattr(self.repository, "fetch_form_analyses"):
            if coach_id is None:
                raise ValueError("coach_id is required for listing form analyses.")
            rows = self.repository.fetch_form_analyses(coach_id, limit, client_id)
        else:
            rows = self.repository.fetch_jobs(limit)
        return [self._row_to_job(row) for row in rows]

    def mark_job_running(self, job_id: str) -> dict[str, Any] | None:
        if hasattr(self.repository, "mark_form_analysis_running"):
            row = self.repository.mark_form_analysis_running(job_id, utc_now())
        else:
            row = self.repository.mark_job_running(job_id, utc_now())
        if row is None:
            return None
        return self._row_to_job(row)

    def mark_job_completed(self, job_id: str, result: dict[str, Any]) -> dict[str, Any] | None:
        now = utc_now()
        kwargs = dict(
            result_json=json.dumps(result),
            error_message=None,
            status="completed",
            updated_at=now,
            completed_at=now,
        )
        if hasattr(self.repository, "update_form_analysis_completion"):
            row = self.repository.update_form_analysis_completion(job_id, **kwargs)
        else:
            row = self.repository.update_job_completion(job_id, **kwargs)
        return self._row_to_job(row) if row else None

    def requeue_job_for_retry(self, job_id: str, error_message: str) -> dict[str, Any] | None:
        kwargs = dict(error_message=error_message, updated_at=utc_now())
        if hasattr(self.repository, "mark_form_analysis_queued_for_retry"):
            row = self.repository.mark_form_analysis_queued_for_retry(job_id, **kwargs)
        else:
            row = self.repository.mark_job_queued_for_retry(job_id, **kwargs)
        return self._row_to_job(row) if row else None

    def mark_job_failed(self, job_id: str, error_message: str) -> dict[str, Any] | None:
        now = utc_now()
        kwargs = dict(
            result_json=None,
            error_message=error_message,
            status="failed",
            updated_at=now,
            completed_at=now,
        )
        if hasattr(self.repository, "update_form_analysis_completion"):
            row = self.repository.update_form_analysis_completion(job_id, **kwargs)
        else:
            row = self.repository.update_job_completion(job_id, **kwargs)
        return self._row_to_job(row) if row else None

    def update_feedback(self, job_id: str, feedback_note: str) -> dict[str, Any] | None:
        if not hasattr(self.repository, "update_form_analysis_feedback"):
            return None
        row = self.repository.update_form_analysis_feedback(job_id, feedback_note, utc_now())
        return self._row_to_job(row) if row else None

    def get_job_for_coach(self, job_id: str, coach_id: int) -> dict[str, Any] | None:
        if not hasattr(self.repository, "fetch_form_analysis_for_coach"):
            return self.get_job(job_id)
        row = self.repository.fetch_form_analysis_for_coach(job_id, coach_id)
        return self._row_to_job(row) if row else None

    def _row_to_job(self, row: dict[str, Any]) -> dict[str, Any]:
        result_json = row["result_json"]
        if isinstance(result_json, str):
            result_payload = json.loads(result_json)
        else:
            result_payload = result_json

        return {
            "id": row["id"],
            "client_id": row.get("client_id"),
            "analysis_type": row["analysis_type"],
            "status": row["status"],
            "original_filename": row["original_filename"],
            "stored_filename": row["stored_filename"],
            "video_blob_name": row["video_blob_name"],
            "result": result_payload,
            "error_message": row["error_message"],
            "coach_feedback_note": row.get("coach_feedback_note"),
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        }
