import json
import logging
import sys
from datetime import UTC, datetime
from functools import lru_cache

from config.features import analysis_enabled
from config.queue_storage_config import get_queue_storage_config
from config.local_settings_loader import load_local_settings
from services.job_runner import JobRunner
from services.job_service import JobService
from services.queue_job_processor import (
    NonRetryableQueueMessageError,
    RetryableQueueProcessingError,
    process_queue_message,
)
from services.queue_service import QueueService

load_local_settings()
logging.basicConfig(level=logging.INFO)


@lru_cache(maxsize=1)
def get_runtime_dependencies() -> tuple[QueueService, JobService, JobRunner]:
    return QueueService(), JobService(), JobRunner()


def build_poison_payload(*, message_id: str, dequeue_count: int, raw_content: str, payload: dict | None, error_message: str) -> dict:
    return {
        "message_id": message_id,
        "dequeue_count": dequeue_count,
        "error_message": error_message,
        "failed_at": datetime.now(UTC).isoformat(),
        "payload": payload,
        "raw_message": raw_content,
    }


def mark_job_failed_if_present(job_service: JobService, payload: dict | None, error_message: str):
    service = scoped_message_service(job_service, payload)
    if service is None:
        return
    job_id = payload.get("analysis_id") or payload.get("job_id")
    if job_id:
        service.mark_job_failed(job_id, error_message)


def scoped_message_service(job_service, payload):
    if not isinstance(payload, dict):
        return None
    organization_id = payload.get("organization_id")
    if type(organization_id) is not int or organization_id <= 0:
        return None
    return job_service.for_organization(organization_id)


def move_message_to_poison_queue(
    *,
    queue_service: QueueService,
    job_service: JobService,
    message,
    payload: dict | None,
    error_message: str,
    fail_claimed_job: bool = False,
):
    queue_service.enqueue_poison_job(
        build_poison_payload(
            message_id=message.id,
            dequeue_count=message.dequeue_count,
            raw_content=message.content,
            payload=payload,
            error_message=error_message,
        )
    )
    if fail_claimed_job:
        mark_job_failed_if_present(job_service, payload, error_message)
    queue_service.delete_analysis_job(message)


def main() -> int:
    if not analysis_enabled():
        logging.info("Form analysis disabled; queue left untouched.")
        return 0
    queue_service, job_service, job_runner = get_runtime_dependencies()
    queue_config = get_queue_storage_config()
    message = queue_service.receive_analysis_job(
        visibility_timeout=queue_config.visibility_timeout_seconds,
    )

    if message is None:
        logging.info("No queue message found. Exiting.")
        return 0

    payload = None

    try:
        payload = json.loads(message.content)
        if not isinstance(payload, dict):
            raise NonRetryableQueueMessageError("Queue message must be an object.")
        analysis_identifier = payload.get("analysis_id") or payload.get("job_id")
        logging.info("Processing analysis queue message for analysis_id=%s", analysis_identifier)
        process_queue_message(job_service, job_runner, payload)
        queue_service.delete_analysis_job(message)
        logging.info("Queue message processed and deleted for analysis_id=%s", analysis_identifier)
        return 0
    except json.JSONDecodeError as exc:
        error_message = f"Invalid queue message JSON: {exc}"
        logging.exception(
            "Queue message is invalid and will be moved to poison queue. message_id=%s",
            message.id,
        )
        move_message_to_poison_queue(
            queue_service=queue_service,
            job_service=job_service,
            message=message,
            payload=payload,
            error_message=error_message,
        )
        return 1
    except NonRetryableQueueMessageError as exc:
        error_message = str(exc)
        logging.exception(
            "Non-retryable queue processing failure. Moving message_id=%s to poison queue.",
            message.id,
        )
        move_message_to_poison_queue(
            queue_service=queue_service,
            job_service=job_service,
            message=message,
            payload=payload,
            error_message=error_message,
        )
        return 1
    except RetryableQueueProcessingError as exc:
        error_message = str(exc)
        analysis_id = payload.get("analysis_id") or payload.get("job_id") if isinstance(payload, dict) else None
        service = scoped_message_service(job_service, payload)
        if analysis_id and service and message.dequeue_count < queue_config.max_dequeue_count:
            service.requeue_job_for_retry(analysis_id, error_message)

        if message.dequeue_count >= queue_config.max_dequeue_count:
            logging.exception(
                "Retry limit reached for message_id=%s. Moving to poison queue.",
                message.id,
            )
            move_message_to_poison_queue(
                queue_service=queue_service,
                job_service=job_service,
                message=message,
                payload=payload,
                error_message=error_message,
                fail_claimed_job=True,
            )
            return 1

        logging.exception(
            "Retryable worker failure for message_id=%s. Message will be retried after visibility timeout.",
            message.id,
        )
        return 1
    except Exception as exc:
        error_message = str(exc)
        # No proof that this path acquired a claim: never mutate a job from
        # untrusted payload identifiers while handling an unexpected error.
        if message.dequeue_count >= queue_config.max_dequeue_count:
            logging.exception(
                "Unexpected failure reached retry limit for message_id=%s. Moving to poison queue.",
                message.id,
            )
            move_message_to_poison_queue(
                queue_service=queue_service,
                job_service=job_service,
                message=message,
                payload=payload,
                error_message=error_message,
            )
            return 1

        logging.exception(
            "Unexpected worker failure for message_id=%s. Message will be retried after visibility timeout.",
            message.id,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
