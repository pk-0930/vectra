"""Explicit recovery for verified queued rows after old messages are quarantined.

Run from mobility-ai-service with its venv, supplying both identifiers. This
never infers ownership, mutates status or replays arbitrary poison payloads.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.local_settings_loader import load_local_settings
from services.job_service import JobService
from services.queue_service import QueueService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--organization-id', type=int, required=True)
    parser.add_argument('--analysis-id', required=True)
    parser.add_argument('--enqueue', action='store_true', help='Send a new scoped message; omitted means read-only verification.')
    args = parser.parse_args()
    load_local_settings()
    service = JobService().for_organization(args.organization_id)
    job = service.get_job(args.analysis_id)
    if job is None or job['status'] != 'queued':
        parser.error('No queued analysis exists in the specified business.')
    if args.enqueue:
        QueueService().enqueue_analysis_job(job_id=job['id'], analysis_type=job['analysis_type'], organization_id=args.organization_id)
        print('Scoped queue message sent.')
    else:
        print('Verified queued analysis. No message sent; use --enqueue after review.')


if __name__ == '__main__':
    main()
