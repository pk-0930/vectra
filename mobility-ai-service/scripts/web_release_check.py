"""Read-only release checks. Uses environment only, never prints secret values.

Run in the target deployment environment. --database checks migration/outbox
metadata without sending email, creating payments or modifying records.
"""
import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.auth_config import get_auth_config
from config.billing_config import get_billing_config
from config.postgres_config import get_postgres_config
from services.email_delivery_service import public_web_url


def configuration_checks(environment):
    checks = {}
    for name, operation in [('authentication', get_auth_config), ('database_configuration', get_postgres_config),
                            ('public_web_url', public_web_url), ('billing_configuration', get_billing_config)]:
        try:
            operation()
            checks[name] = True
        except (ValueError, RuntimeError, TypeError, KeyError):
            checks[name] = False
    config = None
    if checks['billing_configuration']:
        config = get_billing_config()
    checks['billing_enabled'] = bool(config and config.enabled)
    checks['billing_mode'] = bool(config and config.mode == ('live' if environment == 'production' else 'test'))
    checks['email_configured'] = bool(os.environ.get('AZURE_COMMUNICATION_SERVICES_CONNECTION_STRING') and
                                      os.environ.get('AZURE_COMMUNICATION_SERVICES_SENDER_ADDRESS'))
    storage = os.environ.get('AzureWebJobsStorage', '')
    checks['cloud_storage_configured'] = bool(storage and 'UseDevelopmentStorage=true' not in storage)
    checks['https_web_url'] = urlsplit(os.environ.get('PUBLIC_WEB_BASE_URL', '')).scheme == 'https'
    checks['database_tls'] = os.environ.get('POSTGRES_SSLMODE', 'require') in {'require', 'verify-ca', 'verify-full'}
    return checks


def database_checks():
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(**get_postgres_config().connection_kwargs(), connect_timeout=5, row_factory=dict_row) as db:
        db.execute('SET TRANSACTION READ ONLY')
        db.execute("SET LOCAL statement_timeout='10s'")
        migrated = db.execute("SELECT EXISTS(SELECT 1 FROM flyway_schema_history WHERE version='13' AND success) AS ok").fetchone()['ok']
        outbox = db.execute("SELECT status,count(*) AS count FROM email_outbox GROUP BY status").fetchall()
        return {'migration_v13': migrated, 'email_outbox': outbox}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', required=True, choices=['staging', 'production'])
    parser.add_argument('--database', action='store_true')
    args = parser.parse_args()
    checks = configuration_checks(args.environment)
    result = {'environment': args.environment, 'configuration': checks,
              'live_provider_delivery_verified': False, 'pilot_completed': False}
    passed = all(checks.values())
    if args.database:
        try:
            result['database'] = database_checks()
            passed = passed and result['database']['migration_v13']
        except Exception:
            result['database'] = {'error': 'Database/schema check failed; inspect target configuration securely.'}
            passed = False
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
