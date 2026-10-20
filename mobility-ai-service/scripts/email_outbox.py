"""Restricted operator CLI: metadata-only failures, explicit safe requeue."""
import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.local_settings_loader import load_local_settings
from config.postgres_config import get_postgres_config
from repositories.identity_repository import IdentityRepository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--retry', type=UUID, help='Requeue one failed, still-valid action by outbox ID')
    args = parser.parse_args()
    load_local_settings()
    with IdentityRepository(get_postgres_config()).transaction() as db:
        if args.retry:
            rows = db.execute("UPDATE email_outbox e SET status='pending',attempts=0,available_at=now(),error_code=NULL "
                              "WHERE e.id=%s AND e.status='failed' AND (e.billing_notification_id IS NOT NULL OR "
                              "EXISTS(SELECT 1 FROM identity_actions a WHERE a.id=e.action_id AND a.revoked_at IS NULL "
                              "AND a.consumed_at IS NULL AND a.expires_at>now())) RETURNING e.id", (args.retry,)).fetchall()
        else:
            rows = db.execute("SELECT e.id,e.status,e.attempts,e.error_code,e.created_at,COALESCE(a.kind,'billing') AS kind, "
                              "COALESCE(a.organization_id,n.organization_id) AS organization_id "
                              "FROM email_outbox e LEFT JOIN identity_actions a ON a.id=e.action_id "
                              "LEFT JOIN billing_notifications n ON n.id=e.billing_notification_id "
                              "WHERE e.status IN ('pending','failed') ORDER BY e.created_at LIMIT 100").fetchall()
        print(json.dumps(rows, default=str))


if __name__ == '__main__':
    main()
