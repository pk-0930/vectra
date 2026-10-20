"""Durable subscription creation, webhook reconciliation and scheduled provider refresh."""
import argparse
import logging
import time
from config.local_settings_loader import load_local_settings
from config.postgres_config import get_postgres_config
from repositories.billing_repository import BillingRepository
from services.billing_service import BillingService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    load_local_settings()
    service = BillingService(BillingRepository(get_postgres_config()))
    if not service.config.enabled:
        raise SystemExit('Configure Razorpay credentials and the software plan catalogue before starting billing delivery.')
    while True:
        try:
            worked = service.process_one()
        except Exception:
            logging.error('Billing worker storage failure; retrying without logging provider contents.')
            worked = False
        if args.once: return
        if not worked: time.sleep(5)


if __name__ == '__main__':
    main()
