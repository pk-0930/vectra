"""Plan or apply a web release to explicitly named, pre-provisioned Azure resources.

Uses target environment variables for read-only configuration/schema checks.
Never reads local.settings.json. Does not create resources or change secrets.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from web_release_check import configuration_checks, database_checks


def release_commands(args):
    if not re.fullmatch(r'[0-9a-f]{40}', args.commit):
        raise ValueError('Use the full immutable Git commit SHA for both image tags.')
    if not re.fullmatch(r'[a-z0-9.-]+\.azurecr\.io', args.registry):
        raise ValueError('Use the Azure Container Registry login server hostname.')
    base = ['--subscription', args.subscription, '--resource-group', args.resource_group]
    worker = f'{args.registry}/vectra-worker:{args.commit}'
    apps = [(args.api, f'{args.registry}/vectra-api:{args.commit}', None),
            (args.analysis_worker, worker, 'queue_worker.py'),
            (args.email_worker, worker, 'email_worker.py'),
            (args.billing_worker, worker, 'billing_worker.py')]
    commands = []
    for name, image, script in apps:
        command = ['az', 'containerapp', 'update', *base, '--name', name, '--image', image]
        if script:
            command += ['--command', 'python', script, '--min-replicas', '1', '--max-replicas', '1']
        commands.append(command + ['--output', 'none'])
    commands.append(['az', 'containerapp', 'job', 'update', *base, '--name', args.membership_job,
                     '--image', worker, '--command', 'python', 'membership_worker.py', '--output', 'none'])
    return commands


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('subscription', 'resource-group', 'registry', 'commit', 'api', 'analysis-worker',
                 'email-worker', 'billing-worker', 'membership-job', 'api-url'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--environment', required=True, choices=['staging', 'production'])
    parser.add_argument('--apply', action='store_true', help='Execute after schema/configuration checks; default only prints the plan')
    args = parser.parse_args()
    try:
        commands = release_commands(args)
        parsed = urlsplit(args.api_url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('API URL must be HTTPS without credentials, query or fragment.')
    except ValueError as exc:
        parser.error(str(exc))
    if not args.apply:
        print(json.dumps({'environment': args.environment, 'commands': commands}, indent=2))
        return
    checks = configuration_checks(args.environment)
    if not all(checks.values()):
        raise SystemExit('Target configuration failed: ' + ', '.join(k for k, v in checks.items() if not v))
    if not database_checks()['migration_v13']:
        raise SystemExit('Apply and validate Flyway V13 in the target database before releasing containers.')
    # Resolve every named target before changing any resource.
    base = ['--subscription', args.subscription, '--resource-group', args.resource_group]
    for target in (args.api, args.analysis_worker, args.email_worker, args.billing_worker):
        subprocess.run(['az', 'containerapp', 'show', *base, '--name', target, '--query', 'id', '--output', 'none'], check=True)
    subprocess.run(['az', 'containerapp', 'job', 'show', *base, '--name', args.membership_job, '--query', 'id', '--output', 'none'], check=True)
    for command in commands:
        subprocess.run(command, check=True)
    import requests
    response = requests.get(args.api_url.rstrip('/') + '/health/ready', timeout=(5, 20))
    response.raise_for_status()
    if response.json() != {'ready': True}:
        raise SystemExit('API readiness response did not match. Inspect the release before enabling purchases.')
    print('Container updates and API readiness passed. Verify worker executions and live provider evidence separately.')


if __name__ == '__main__':
    main()
