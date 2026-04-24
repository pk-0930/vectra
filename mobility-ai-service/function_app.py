import json
import logging
from functools import lru_cache

import azure.functions as func

from config.queue_storage_config import get_queue_storage_config
from services.job_runner import JobRunner
from services.queue_job_processor import process_queue_message
from services.job_store import JobStore

app = func.FunctionApp()


@lru_cache(maxsize=1)
def get_runtime_dependencies() -> tuple[JobStore, JobRunner]:
    return JobStore(), JobRunner()


@app.queue_trigger(
    arg_name="msg",
    queue_name=get_queue_storage_config().queue_name,
    connection="AzureWebJobsStorage",
)
def process_analysis_job(msg: func.QueueMessage) -> None:
    try:
        payload = json.loads(msg.get_body().decode("utf-8"))
        logging.info("Processing analysis queue message for job_id=%s", payload.get("job_id"))
        job_store, job_runner = get_runtime_dependencies()
        processed = process_queue_message(job_store, job_runner, payload)
    except Exception:
        logging.exception(
            "Queue processing crashed for job_id=%s",
            payload.get("job_id"),
        )
        raise

    if not processed:
        logging.error(
            "Queue processing failed for job_id=%s. Job marked as failed in persistence.",
            payload.get("job_id"),
        )
