import json
import logging
import os
import sys

from azure.storage.queue import QueueClient

from config.local_settings_loader import load_local_settings
from services.job_runner import JobRunner
from services.job_store import JobStore
from services.queue_job_processor import process_queue_message

load_local_settings()
logging.basicConfig(level=logging.INFO)


def get_queue_client() -> QueueClient:
    return QueueClient.from_connection_string(
        conn_str=os.environ["AZURE_STORAGE_CONNECTION_STRING"],
        queue_name=os.environ.get("ANALYSIS_JOBS_QUEUE_NAME", "analysis-jobs"),
    )


def main() -> int:
    queue_client = get_queue_client()

    messages = queue_client.receive_messages(
        messages_per_page=1,
        visibility_timeout=1800,
    )

    message = next(iter(messages), None)

    if message is None:
        logging.info("No queue message found. Exiting.")
        return 0

    try:
        raw = message.content
        logging.info("Received queue message: %s", raw)

        payload = json.loads(raw)

        job_store = JobStore()
        job_runner = JobRunner()

        process_queue_message(job_store, job_runner, payload)

        queue_client.delete_message(message)
        logging.info("Queue message processed and deleted.")

        return 0

    except Exception:
        logging.exception("Worker failed. Message will be retried after visibility timeout.")
        return 1


if __name__ == "__main__":
    sys.exit(main())