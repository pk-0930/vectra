"""Run daily to enqueue expiry notices; does not contact email/payment providers."""
from config.local_settings_loader import load_local_settings
from config.postgres_config import get_postgres_config
from repositories.membership_repository import MembershipRepository
from services.membership_service import MembershipService


if __name__ == '__main__':
    load_local_settings()
    print(MembershipService(MembershipRepository(get_postgres_config())).reminders())
