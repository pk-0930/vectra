from services.job_runner import JobRunner
from services.job_service import JobService
import logging


class NonRetryableQueueMessageError(Exception):
    pass


class RetryableQueueProcessingError(Exception):
    pass


def process_queue_message(job_service: JobService, job_runner: JobRunner, message: dict) -> bool:
    if not isinstance(message, dict):
        raise NonRetryableQueueMessageError("Queue message must be an object.")
    organization_id = message.get("organization_id")
    if type(organization_id) is not int or organization_id <= 0:
        raise NonRetryableQueueMessageError("Queue message requires a valid organization_id.")
    job_service = job_service.for_organization(organization_id)
    job_id = message.get("analysis_id") or message.get("job_id")
    analysis_type = message.get("analysis_type")

    if not job_id:
        raise NonRetryableQueueMessageError("Queue message is missing analysis_id.")

    if analysis_type != "squat":
        raise NonRetryableQueueMessageError(f"Unsupported analysis type: {analysis_type}")

    logging.info("mark runing, Start")
    job = job_service.mark_job_running(job_id)
    logging.info("runnin...")
    if job is None:
        existing_job = job_service.get_job(job_id)
        if existing_job is None:
            raise NonRetryableQueueMessageError(f"Job not found for job_id={job_id}")
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
        job_service.mark_job_completed(job_id, result)
    except Exception as exc:
        raise RetryableQueueProcessingError(str(exc)) from exc

    return True
