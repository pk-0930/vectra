import argparse
import json

from services.job_runner import JobRunner
from services.job_store import JobStore


def process_queue_message(job_store: JobStore, job_runner: JobRunner, message: dict) -> bool:
    job_id = message.get("job_id")
    analysis_type = message.get("analysis_type")

    if not job_id:
        raise ValueError("Queue message is missing job_id.")

    if analysis_type != "squat":
        raise ValueError(f"Unsupported analysis type: {analysis_type}")

    job = job_store.mark_job_running(job_id)
    if job is None:
        existing_job = job_store.get_job(job_id)
        return existing_job is not None and existing_job["status"] in {"running", "completed"}

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
        raise

    return True


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
