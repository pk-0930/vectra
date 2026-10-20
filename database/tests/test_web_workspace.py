"""Isolated PostgreSQL web delivery acceptance and migration rehearsal."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4
import unittest
from unittest.mock import patch
import test_organization_foundations as foundations
import test_pt_appointments as pt_tests
from repositories.access_repository import AccessDenied, ResourceNotFound
from services.web_workspace_service import WebWorkspaceService
from services.membership_service import today_india
from services.plan_service import PlanService
from config.postgres_config import PostgresConfig


@unittest.skipUnless(foundations.ENABLED, 'Set VECTRA_RUN_MIGRATION_TESTS=1')
class WebWorkspaceTests(foundations.DisposablePostgresTests):
    new_user = pt_tests.PtTests.new_user
    role = pt_tests.PtTests.role
    png = staticmethod(pt_tests.PtTests.png)
    access = pt_tests.PtTests.access
    payload = pt_tests.PtTests.payload
    join = pt_tests.PtTests.join
    pay = pt_tests.PtTests.pay
    pt_purchase = pt_tests.PtTests.pt_purchase
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.create_database('web')
        cls.flyway('web', 'migrate')
        cls.flyway('web', 'validate')
        cls.config = PostgresConfig(host='127.0.0.1', port=cls.port, dbname='web',
                                   user='postgres', password=cls.password, sslmode='disable')

    def setUp(self):
        pt_tests.PtTests.setUp(self)
        self.web = WebWorkspaceService()

    def test_inbox_payment_retry_read_scope_and_pagination(self):
        purchase = self.pt_purchase()
        self.pay(purchase); self.pay(purchase)
        with self.access(self.member) as access:
            page = self.web.inbox(access, limit=1)
            self.assertEqual(page['unread'], 2)
            self.assertIsNotNone(page['next_before'])
            identifier = page['items'][0]['id']
            self.assertEqual(len(self.web.inbox(access, page['next_before'])['items']), 1)
            first = self.web.mark_read(access, identifier)
            self.assertEqual(first, self.web.mark_read(access, identifier))
            self.assertEqual(self.web.inbox(access)['unread'], 1)
        with self.assertRaises(ResourceNotFound), self.access(self.owner) as access:
            self.web.mark_read(access, identifier)

    def test_announcement_audiences_concurrency_and_permissions(self):
        identifier = uuid4()
        def send(_):
            with self.access(self.owner) as access:
                return self.web.announce(access, identifier, 'trainers', 'Hours changed', 'Open at 8am.')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(send, range(2)))
        self.assertEqual(results[0], results[1]); self.assertEqual(results[0]['recipient_count'], 1)
        with self.access(self.trainer) as access:
            self.assertEqual(len(self.web.inbox(access)['items']), 1)
            with self.assertRaises(AccessDenied): self.web.announce(access, uuid4(), 'all', 'No', 'No')
            with self.assertRaises(AccessDenied): self.web.reports(access)
        with self.access(self.owner, member=True) as access:
            with self.assertRaises(AccessDenied): self.web.announce(access, uuid4(), 'all', 'No', 'No')
        with self.access(self.member) as access:
            self.assertFalse(any(i['subject'] == 'Hours changed' for i in self.web.inbox(access)['items']))
        with self.access(self.owner) as access:
            with self.assertRaises(ValueError): self.web.announce(access, identifier, 'all', 'Changed', 'No')
            self.assertEqual(self.web.announce(access, uuid4(), 'members', 'Member update', 'Hello')['recipient_count'], 1)

    def test_reports_reconcile_refunds_and_do_not_count_pending_as_cash(self):
        pending = self.pt_purchase()
        paid = self.pt_purchase(); self.pay(paid)
        for purchase in (pending, paid):
            with self.access(self.owner) as access:
                self.memberships.act(access, purchase['id'], 'refund', {
                    'note': 'Externally returned', 'reference': uuid4().hex,
                    'amount_paise': purchase['amount_paise'], 'external_refund_completed': True,
                    'entitlement': 'revoke'}, True)
        with self.access(self.owner) as access:
            result = self.web.reports(access)
            self.assertEqual(sum(r['amount_paise'] for r in result['collections']), 24690)
            self.assertEqual({r['verified_collection']: r['amount_paise'] for r in result['refunds']}, {True: 12345, False: 12345})
            self.assertEqual(result['memberships']['active_members'], 1)
            self.assertEqual(result['pt_purchases'][0]['purchases'], 2)
            with self.assertRaises(ValueError): self.web.reports(access, today_india(), today_india()-timedelta(days=1))

    def test_published_plan_goal_privacy_and_expired_history(self):
        purchase = self.pt_purchase(); result = self.pay(purchase)
        client = result['pt']['client_id']
        with self.access(self.owner) as access:
            plan = PlanService(access).create_plan('workout', self.owner['id'], client, {
                'title': 'Published', 'period_type': 'weekly', 'period_start': str(today_india()),
                'period_end': str(today_india()+timedelta(days=7)), 'content': {'workout': 'Squats'}})
            access.add_client_goal({'client_id': client, 'goal_type': 'strength', 'notes': 'Private notes', 'is_current': True, 'created_at': today_india()})
        with self.access(self.member, member=True) as access:
            self.assertTrue(access.coaching_access(client)['can_upload'])
            self.assertIsNone(access.list_goals(client)[0]['notes'])
            with self.assertRaises(AccessDenied): access.list_plan_drafts(client)
        with self.repo.transaction() as db:
            db.execute('UPDATE pt_entitlements SET starts_on=%s,ends_before=%s WHERE purchase_id=%s',
                       (today_india()-timedelta(days=30), today_india(), purchase['id']))
        with self.access(self.member, member=True) as access:
            self.assertFalse(access.coaching_access(client)['can_upload'])
            with self.assertRaises(AccessDenied): access.require_coaching_upload(client)
            self.assertEqual(PlanService(access).get_plan('workout', self.member['id'], plan['id'])['title'], 'Published')
            self.assertTrue(any(i['subject'] == 'Your coaching plan is ready' for i in self.web.inbox(access)['items']))
        with self.assertRaises(ResourceNotFound), self.access(self.trainer) as access:
            access.fetch_plan('workout_plans', plan['id']+999999)

    def test_pause_blocks_new_purchases_preserves_resolution(self):
        pending = self.pt_purchase()
        with self.access(self.owner) as access: self.web.set_rollout(access, False)
        self.assertFalse(self.service.public(self.public_id)['available'])
        with self.assertRaises(ValueError): self.pt_purchase()
        self.assertEqual(self.pay(pending)['purchase']['status'], 'confirmed')
        with self.assertRaises(AccessDenied), self.access(self.admin) as access: self.web.set_rollout(access, True)
        with self.access(self.owner) as access: self.web.set_rollout(access, True)
        self.assertTrue(self.service.public(self.public_id)['available'])

    def test_reminder_inbox_deduplication(self):
        with self.repo.transaction() as db:
            db.execute('UPDATE gym_membership_periods SET ends_before=%s WHERE organization_id=%s', (today_india()+timedelta(days=7), self.org))
        self.memberships.reminders(); self.memberships.reminders()
        with self.access(self.member) as access:
            items = self.web.inbox(access)['items']
            self.assertEqual(sum(i['subject'] == 'Gym membership expires soon' for i in items), 1)

    def test_upgrade_backfill_backup_restore_and_previous_app_schema(self):
        import subprocess
        source, restored = 'upgrade_' + uuid4().hex[:8], 'restore_' + uuid4().hex[:8]
        self.create_database(source)
        self.flyway(source, 'migrate', '-target=11')
        with self.connect(source) as db:
            user = db.execute("INSERT INTO users(email,password_hash,created_at,updated_at) VALUES('restore@example.invalid','fixture',now(),now()) RETURNING id").fetchone()[0]
            org = db.execute("INSERT INTO organizations(name,organization_type) VALUES('Upgrade fixture','gym') RETURNING id").fetchone()[0]
            rel = db.execute('INSERT INTO organization_relationships(organization_id,user_id) VALUES(%s,%s) RETURNING id', (org, user)).fetchone()[0]
            db.execute("INSERT INTO billing_notifications(id,organization_id,recipient,event_key,subject,message) VALUES(%s,%s,'restore@example.invalid','fixture-upgrade','Prior notice','Preserved message')", (uuid4(), org))
        self.flyway(source, 'migrate'); self.flyway(source, 'validate')
        with self.connect(source) as db:
            self.assertEqual(db.execute('SELECT relationship_id,message FROM notification_inbox').fetchall(), [(rel, 'Preserved message')])
            # Prior application writes still work against the expanded schema.
            db.execute("INSERT INTO billing_notifications(id,organization_id,recipient,event_key,subject,message) VALUES(%s,%s,'restore@example.invalid','fixture-after','After upgrade','Still compatible')", (uuid4(), org))
        dump = self.docker('exec', self.resource, 'pg_dump', '-U', 'postgres', '-d', source)
        self.create_database(restored)
        process = subprocess.run(['docker', 'exec', '-i', self.resource, 'psql', '-U', 'postgres', '-d', restored, '-v', 'ON_ERROR_STOP=1'], input=dump, text=True, capture_output=True, timeout=60)
        self.assertEqual(process.returncode, 0, 'Restore failed in disposable database')
        self.flyway(restored, 'validate')
        with self.connect(restored) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM notification_inbox').fetchone()[0], 2)
            self.assertEqual(db.execute('SELECT count(*) FROM billing_notifications').fetchone()[0], 2)

    def test_verified_client_invitation_links_only_selected_profile_without_staff_role(self):
        import secrets
        from services.identity_service import IdentityService
        from services.security_service import SecurityService
        from config.auth_config import AuthConfig
        identity = IdentityService(self.repo, SecurityService(AuthConfig(secrets.token_urlsafe(32), 24)))
        email = uuid4().hex + '@example.invalid'
        with self.access(self.owner) as access:
            client = access.create_client({'first_name': 'Online', 'last_name': 'Client', 'is_active': True,
                                           'created_at': today_india(), 'updated_at': today_india()})
            identity.create_invitation(access, email, 'client', client['id'])
            action = access.connection.execute('SELECT id FROM identity_actions WHERE organization_id=%s AND email=%s', (self.org, email)).fetchone()['id']
        with self.assertRaises(ValueError):
            identity.consume(identity.token(action), 'invite', email='wrong@example.invalid', password='Synthetic-only-password')
        identity.consume(identity.token(action), 'invite', email=email, password='Synthetic-only-password')
        with self.repo.transaction() as db:
            user = db.execute('SELECT * FROM users WHERE email=%s', (email,)).fetchone()
            rel = db.execute('SELECT id FROM organization_relationships WHERE organization_id=%s AND user_id=%s', (self.org, user['id'])).fetchone()['id']
            self.assertEqual(db.execute('SELECT organization_relationship_id FROM clients WHERE id=%s', (client['id'],)).fetchone()['organization_relationship_id'], rel)
            self.assertEqual(db.execute('SELECT count(*) AS n FROM organization_staff_roles WHERE relationship_id=%s', (rel,)).fetchone()['n'], 0)
            # Independent-coaching businesses never gain a gym-membership gate.
            db.execute("UPDATE organizations SET organization_type='coaching' WHERE id=%s", (self.org,))
        with self.access(user) as access:
            self.assertTrue(access.coaching_access(client['id'])['can_upload'])
        with self.assertRaises(ValueError): identity.consume(identity.token(action), 'invite', email=email, current_user=user)
        with self.assertRaises(ValueError), self.access(self.owner) as access:
            identity.create_invitation(access, uuid4().hex+'@example.invalid', 'client', client['id'])

    def test_http_web_authorization_and_validation(self):
        import asyncio
        import importlib.util
        import json
        import secrets
        from contextlib import ExitStack
        from unittest.mock import patch
        from config.auth_config import AuthConfig
        from services.auth_service import AuthService
        from services.security_service import SecurityService
        with ExitStack() as stack:
            stack.enter_context(patch('config.local_settings_loader.load_local_settings'))
            for mod, name in [('auth_service', 'AuthService'), ('client_service', 'ClientService'),
                              ('plan_service', 'PlanService'), ('job_service', 'JobService'),
                              ('job_runner', 'JobRunner'), ('blob_storage_service', 'BlobStorageService'),
                              ('queue_service', 'QueueService'), ('ai_plan_draft_service', 'AiPlanDraftService'),
                              ('pdf_service', 'PdfService'), ('storage_asset_service', 'StorageAssetService')]:
                stack.enter_context(patch(f'services.{mod}.{name}'))
            spec = importlib.util.spec_from_file_location('web_test_app', foundations.ROOT / 'mobility-ai-service/app.py')
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        security = SecurityService(AuthConfig(secrets.token_urlsafe(32), 24))
        module.auth_service = AuthService(self.repo, security)
        module.billing_service = self.billing

        def request(path, user=None, method='GET', body=None, org=None, mode='staff', query=b''):
            async def run():
                messages = []
                raw = json.dumps(body).encode() if body is not None else b''
                async def receive(): return {'type': 'http.request', 'body': raw, 'more_body': False}
                async def send(message): messages.append(message)
                headers = [(b'content-type', b'application/json'), (b'x-organization-id', str(org or self.org).encode()), (b'x-access-mode', mode.encode())]
                if user:
                    headers.append((b'authorization', ('Bearer ' + security.create_access_token(user_id=user['id'], email=user['email'])).encode()))
                await module.app({'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'}, 'http_version': '1.1',
                                  'method': method, 'scheme': 'http', 'path': path, 'raw_path': path.encode(), 'query_string': query,
                                  'root_path': '', 'headers': headers, 'client': ('test', 1), 'server': ('test', 80)}, receive, send)
                status = next(m['status'] for m in messages if m['type'] == 'http.response.start')
                payload = b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body')
                return status, json.loads(payload)
            return asyncio.run(run())

        self.assertEqual(request('/health/ready'), (200, {'ready': True}))
        self.assertEqual(request('/inbox')[0], 401)
        self.assertEqual(request('/inbox', self.member, org=999999)[0], 403)
        self.assertEqual(request('/inbox', self.member, query=b'limit=10000')[0], 422)
        self.assertEqual(request('/organization/reports', self.owner)[0], 200)
        self.assertEqual(request('/organization/reports', self.trainer)[0], 403)
        self.assertEqual(request('/organization/reports', self.owner, mode='member')[0], 403)
        self.assertEqual(request('/organization/reports', self.member)[0], 403)
        self.assertEqual(request('/organization/reports', self.owner, query=b'start=invalid')[0], 422)
        self.assertEqual(request('/organization/announcements', self.trainer, 'POST', {'request_id': str(uuid4()), 'audience': 'all', 'subject': 'No', 'message': 'No'})[0], 403)
        status, inbox = request('/inbox', self.member)
        self.assertEqual(status, 200)
        item = inbox['items'][0]['id']
        self.assertEqual(request(f'/inbox/{item}/read', self.owner, 'POST')[0], 404)
        self.assertEqual(request(f'/inbox/{item}/read', self.member, 'POST')[0], 200)
        self.assertEqual(request('/organization/web-rollout', self.admin, 'PUT', {'purchases_enabled': False})[0], 403)
        self.assertEqual(request('/organization/web-rollout', self.owner, 'PUT', {'purchases_enabled': 'false'})[0], 422)
        with self.repo.transaction() as db:
            db.execute("UPDATE organizations SET billing_legacy_until=now()-interval '1 day' WHERE id=%s", (self.org,))
        self.assertEqual(request('/organization/announcements', self.owner, 'POST', {'request_id': str(uuid4()), 'audience': 'all', 'subject': 'No', 'message': 'No'})[0], 402)
        self.assertEqual(request('/inbox', self.member)[0], 200)

    def test_analysis_switch_filters_inbox_and_unread_without_deleting_history(self):
        with self.access(self.member) as access:
            baseline = self.web.inbox(access)
            for key in ('analysis:old', 'announcement:keep'):
                access.connection.execute(
                    'INSERT INTO notification_inbox(organization_id,relationship_id,event_key,subject,message) '
                    'VALUES(%s,%s,%s,%s,%s)',
                    (access.organization_id, access.context['id'], key, key, 'Saved history'))
            with patch.dict('os.environ', {'FORM_ANALYSIS_ENABLED': 'false'}):
                page = self.web.inbox(access, limit=1)
                self.assertEqual(page['unread'], baseline['unread'] + 1)
                self.assertEqual(page['items'][0]['subject'], 'announcement:keep')
                remaining = self.web.inbox(access, page['next_before'])
                self.assertFalse(any(item['subject'] == 'analysis:old' for item in remaining['items']))
            with patch.dict('os.environ', {'FORM_ANALYSIS_ENABLED': 'true'}):
                page = self.web.inbox(access)
                self.assertEqual(page['unread'], baseline['unread'] + 2)
                self.assertEqual(len(page['items']), len(baseline['items']) + 2)
