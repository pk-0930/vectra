from datetime import UTC, datetime
import unittest
from unittest.mock import Mock, patch

from services.job_store import JobStore
from worker import process_queue_message


class InMemoryJobRepository:
    def __init__(self):
        self.jobs: dict[str, dict] = {}

    def initialize(self):
        return None

    def insert_job(self, payload: dict) -> dict:
        self.jobs[payload["id"]] = dict(payload)
        return dict(self.jobs[payload["id"]])

    def fetch_job(self, job_id: str) -> dict | None:
        job = self.jobs.get(job_id)
        return dict(job) if job else None

    def fetch_jobs(self, limit: int) -> list[dict]:
        ordered_jobs = sorted(
            self.jobs.values(),
            key=lambda job: job["created_at"],
            reverse=True,
        )
        return [dict(job) for job in ordered_jobs[:limit]]

    def mark_job_running(self, job_id: str, started_at: datetime) -> dict | None:
        job = self.jobs.get(job_id)
        if job is None or job["status"] != "queued":
            return None

        job["status"] = "running"
        job["started_at"] = started_at
        job["updated_at"] = started_at
        return dict(job)

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
        job = self.jobs.get(job_id)
        if job is None:
            return None

        job["status"] = status
        job["result_json"] = result_json
        job["error_message"] = error_message
        job["updated_at"] = updated_at
        job["completed_at"] = completed_at
        return dict(job)


class JobStoreTests(unittest.TestCase):
    def build_store(self) -> JobStore:
        return JobStore(repository=InMemoryJobRepository())

    def test_job_lifecycle_moves_from_queued_to_completed(self):
        store = self.build_store()
        job = store.create_job(
            job_id="job-1",
            analysis_type="squat",
            original_filename="demo.mp4",
            stored_filename="job-1_demo.mp4",
            video_blob_name="job-1/job-1_demo.mp4",
        )

        self.assertEqual(job["status"], "queued")

        running_job = store.mark_job_running("job-1")

        self.assertEqual(running_job["id"], "job-1")
        self.assertEqual(running_job["status"], "running")

        completed_job = store.mark_job_completed(
            "job-1",
            {"status": "Video processed", "analysis_type": "squat"},
        )

        self.assertEqual(completed_job["status"], "completed")
        self.assertEqual(completed_job["result"]["analysis_type"], "squat")

    def test_worker_processes_next_job_and_updates_result(self):
        store = self.build_store()
        store.create_job(
            job_id="job-2",
            analysis_type="squat",
            original_filename="demo.mp4",
            stored_filename="job-2_demo.mp4",
            video_blob_name="job-2/job-2_demo.mp4",
        )

        with patch(
            "services.job_runner.JobRunner.run_squat_job",
            return_value={"status": "Video processed", "filename": "demo.mp4"},
        ):
            processed = process_queue_message(
                store,
                Mock(run_squat_job=Mock(return_value={"status": "Video processed", "filename": "demo.mp4"})),
                {"job_id": "job-2", "analysis_type": "squat"},
            )

        self.assertTrue(processed)
        updated_job = store.get_job("job-2")
        self.assertEqual(updated_job["status"], "completed")
        self.assertEqual(updated_job["result"]["filename"], "demo.mp4")

    def test_worker_marks_job_failed_when_runner_raises(self):
        store = self.build_store()
        store.create_job(
            job_id="job-3",
            analysis_type="squat",
            original_filename="demo.mp4",
            stored_filename="job-3_demo.mp4",
            video_blob_name="job-3/job-3_demo.mp4",
        )

        with self.assertRaises(RuntimeError):
            process_queue_message(
                store,
                Mock(run_squat_job=Mock(side_effect=RuntimeError("processing failed"))),
                {"job_id": "job-3", "analysis_type": "squat"},
            )

        failed_job = store.get_job("job-3")
        self.assertEqual(failed_job["status"], "failed")
        self.assertEqual(failed_job["error_message"], "processing failed")

    def test_list_jobs_returns_most_recent_first(self):
        store = self.build_store()
        repository = store.repository

        older_time = datetime(2026, 4, 23, 9, 0, tzinfo=UTC)
        newer_time = datetime(2026, 4, 23, 10, 0, tzinfo=UTC)

        with patch("services.job_store.utc_now", side_effect=[older_time, newer_time]):
            store.create_job(
                job_id="job-older",
                analysis_type="squat",
                original_filename="older.mp4",
                stored_filename="job-older_older.mp4",
                video_blob_name="job-older/job-older_older.mp4",
            )
            store.create_job(
                job_id="job-newer",
                analysis_type="squat",
                original_filename="newer.mp4",
                stored_filename="job-newer_newer.mp4",
                video_blob_name="job-newer/job-newer_newer.mp4",
            )

        jobs = store.list_jobs(limit=10)

        self.assertEqual([job["id"] for job in jobs], ["job-newer", "job-older"])
        self.assertIsInstance(repository, InMemoryJobRepository)

    def test_worker_ignores_already_completed_job_message(self):
        store = self.build_store()
        store.create_job(
            job_id="job-4",
            analysis_type="squat",
            original_filename="demo.mp4",
            stored_filename="job-4_demo.mp4",
            video_blob_name="job-4/job-4_demo.mp4",
        )
        store.mark_job_running("job-4")
        store.mark_job_completed("job-4", {"status": "done"})

        processed = process_queue_message(
            store,
            Mock(run_squat_job=Mock()),
            {"job_id": "job-4", "analysis_type": "squat"},
        )

        self.assertTrue(processed)


if __name__ == "__main__":
    unittest.main()
