import json
import logging

import azure.functions as func

from services.job_runner import JobRunner
from services.job_store import JobStore
from worker import process_queue_message


app = func.FunctionApp()
job_store = JobStore()
job_runner = JobRunner()


@app.queue_trigger(
    arg_name="msg",
    queue_name="analysis-jobs",
    connection="AzureWebJobsStorage",
)
def process_analysis_job(msg: func.QueueMessage) -> None:
    payload = json.loads(msg.get_body().decode("utf-8"))
    logging.info("Processing analysis queue message for job_id=%s", payload.get("job_id"))
    process_queue_message(job_store, job_runner, payload)
