from services.job_runner import JobRunner
from services.job_store import JobStore
import logging


def process_queue_message(job_store: JobStore, job_runner: JobRunner, message: dict) -> bool:
    logging.info("process queue message ENTER")
    job_id = message.get("job_id")
    analysis_type = message.get("analysis_type")

    if not job_id:
        raise ValueError("Queue message is missing job_id.")

    if analysis_type != "squat":
        raise ValueError(f"Unsupported analysis type: {analysis_type}")
    
    logging.info("mark runing, Start")
    job = job_store.mark_job_running(job_id)
    logging.info("runnin...")
    if job is None:
        existing_job = job_store.get_job(job_id)
        return existing_job is not None and existing_job["status"] in {
            "running",
            "completed",
            "failed",
        }

    try:
        result = job_runner.run_squat_job(
            video_blob_name=job["video_blob_name"],
            original_filename=job["original_filename"],
            stored_filename=job["stored_filename"],
            job_id=job_id,
        )
        job_store.mark_job_completed(job_id, result)
    except Exception as exc:
        job_store.mark_job_failed(job_id, str(exc))
        return False

    return True
