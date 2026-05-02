import json
import logging
import sys
from functools import lru_cache

from config.local_settings_loader import load_local_settings
from services.job_runner import JobRunner
from services.job_store import JobStore
from services.queue_job_processor import process_queue_message
from services.queue_service import QueueService

load_local_settings()
logging.basicConfig(level=logging.INFO)


@lru_cache(maxsize=1)
def get_runtime_dependencies() -> tuple[QueueService, JobStore, JobRunner]:
    return QueueService(), JobStore(), JobRunner()


def main() -> int:
    queue_service, job_store, job_runner = get_runtime_dependencies()
    message = queue_service.receive_analysis_job(visibility_timeout=1800)

    if message is None:
        logging.info("No queue message found. Exiting.")
        return 0

    try:
        payload = json.loads(message.content)
        logging.info("Processing analysis queue message for job_id=%s", payload.get("job_id"))
        processed = process_queue_message(job_store, job_runner, payload)
        if not processed:
            logging.error(
                "Queue processing failed for job_id=%s. Job marked as failed in persistence.",
                payload.get("job_id"),
            )
        queue_service.delete_analysis_job(message)
        logging.info("Queue message processed and deleted for job_id=%s", payload.get("job_id"))

        return 0

    except Exception:
        logging.exception(
            "Worker failed for message_id=%s. Message will be retried after visibility timeout.",
            message.id,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
