import argparse
import json

from config.local_settings_loader import load_local_settings
from services.job_runner import JobRunner
from services.queue_job_processor import process_queue_message
from services.job_store import JobStore

load_local_settings()


def main():
    parser = argparse.ArgumentParser(description="Vectra queue-driven worker")
    parser.add_argument("--message")
    parser.add_argument("--job-id")
    parser.add_argument("--analysis-type", default="squat")
    args = parser.parse_args()

    if not args.message and not args.job_id:
        raise SystemExit("Provide either --message or --job-id.")

    if args.message:
        message = json.loads(args.message)
    else:
        message = {
            "job_id": args.job_id,
            "analysis_type": args.analysis_type,
        }

    job_store = JobStore()
    job_runner = JobRunner()
    process_queue_message(job_store, job_runner, message)


if __name__ == "__main__":
    main()
