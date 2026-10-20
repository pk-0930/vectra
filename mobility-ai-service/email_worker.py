"""Run independently from analysis workers: python email_worker.py [--once]."""
import argparse
import logging
import time

from config.local_settings_loader import load_local_settings
from config.postgres_config import get_postgres_config
from repositories.identity_repository import IdentityRepository
from services.email_delivery_service import AcsEmailAdapter, EmailDeliveryService, public_web_url
from services.identity_service import IdentityService
from services.security_service import SecurityService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    load_local_settings()
    # SDK HTTP logging must never expose email links or credentials.
    logging.getLogger('azure').setLevel(logging.CRITICAL)
    repository = IdentityRepository(get_postgres_config())
    service = EmailDeliveryService(repository, IdentityService(repository, SecurityService()),
                                   AcsEmailAdapter(), public_web_url())
    while True:
        try:
            worked = service.process_one()
        except Exception:
            logging.error('Email worker storage operation failed; retrying. No message contents logged.')
            worked = False
        if args.once:
            return
        if not worked:
            time.sleep(5)


if __name__ == '__main__':
    main()
