"""Operator-only reconciliation. No payment/refund initiation is exposed here."""
import argparse
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sys
from uuid import UUID
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.local_settings_loader import load_local_settings
from config.postgres_config import get_postgres_config
from repositories.billing_repository import BillingRepository
from services.billing_service import BillingService


def main():
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--retry', type=UUID, help='Reschedule reconciliation; never blindly creates another remote subscription')
    actions.add_argument('--resolve-creation', type=UUID, help='Discover and attach a previously created remote subscription')
    actions.add_argument('--legacy-organization', type=int, help='Schedule a legacy transition with at least 30 days notice')
    parser.add_argument('--legacy-until', help='UTC ISO timestamp for the transition deadline')
    parser.add_argument('--confirm-no-remote', action='store_true', help='With resolve-creation: operator has checked the merchant dashboard and confirms no remote subscription exists')
    args = parser.parse_args()
    load_local_settings()
    repo = BillingRepository(get_postgres_config())
    service = BillingService(repo)
    if args.retry:
        with repo.transaction() as db:
            row = db.execute('UPDATE software_subscriptions SET next_sync_at=now() WHERE id=%s RETURNING organization_id', (args.retry,)).fetchone()
            if not row: raise SystemExit('Subscription not found.')
            db.execute("INSERT INTO billing_operator_audit(organization_id,operation,detail) VALUES(%s,'retry',%s)", (row['organization_id'], str(args.retry)))
    elif args.resolve_creation:
        with repo.transaction() as db:
            row = db.execute('SELECT * FROM software_subscriptions WHERE id=%s', (args.resolve_creation,)).fetchone()
        if not row or row['mode'] != service.config.mode or row['provider_id'] or row['status'] not in {'creating','creation_unknown'}:
            raise SystemExit('Only an unresolved creation in the configured mode can be reconciled.')
        remote = service.provider.find_creation(row)
        if remote:
            service.validate_subscription(row, remote)
        elif not args.confirm_no_remote:
            raise SystemExit('No remote match found. Inspect the merchant dashboard before using --confirm-no-remote.')
        with repo.transaction() as db:
            current = db.execute('SELECT * FROM software_subscriptions WHERE id=%s FOR UPDATE', (row['id'],)).fetchone()
            if current['status'] not in {'creating','creation_unknown'} or current['provider_id'] or (current['lease_until'] and current['lease_until'] > datetime.now(UTC)):
                raise SystemExit('Subscription changed or a worker is active; retry later.')
            if remote:
                db.execute('UPDATE software_subscriptions SET provider_id=%s,status=%s,next_sync_at=now(),error_code=NULL WHERE id=%s',
                           (remote['id'], remote['status'], row['id']))
            else:
                db.execute("UPDATE software_subscriptions SET status='creation_failed',closed_at=now(),error_code='operator_confirmed_no_remote' WHERE id=%s", (row['id'],))
            db.execute("INSERT INTO billing_operator_audit(organization_id,operation,detail) VALUES(%s,'resolve_creation',%s)",
                       (row['organization_id'], str(row['id']) + (':attached' if remote else ':confirmed_absent')))
    elif args.legacy_organization:
        if not args.legacy_until: raise SystemExit('--legacy-until is required.')
        until = datetime.fromisoformat(args.legacy_until)
        if until.tzinfo is None or until < datetime.now(UTC)+timedelta(days=30):
            raise SystemExit('Provide an explicit timezone and at least 30 days notice.')
        with repo.transaction() as db:
            org = repo.organization(db, args.legacy_organization, lock=True)
            if not org or org['billing_required']: raise SystemExit('Not a legacy organization.')
            db.execute('UPDATE organizations SET billing_legacy_until=%s WHERE id=%s', (until, org['id']))
            repo.notify_owners(db, org['id'], 'legacy:'+until.isoformat(), 'Vectra software transition notice',
                               f"Legacy access for {org['name']} ends at {until.isoformat()}. Choose a software plan in Billing to continue making changes. Existing records remain readable.")
            db.execute("INSERT INTO billing_operator_audit(organization_id,operation,detail) VALUES(%s,'legacy_transition',%s)", (org['id'], until.isoformat()))
    else:
        print(json.dumps(repo.operator_report(), default=str))


if __name__ == '__main__':
    main()
