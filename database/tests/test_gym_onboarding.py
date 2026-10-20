"""Real PostgreSQL boundaries for gym publishing, public identity linking and snapshots."""
import copy
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from io import BytesIO
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4
from PIL import Image
import psycopg
import test_organization_foundations as foundations
sys.path.insert(0, str(foundations.ROOT / 'mobility-ai-service'))
sys.path.insert(0, str(foundations.ROOT / 'mobility-ai-service/tests'))
from config.postgres_config import PostgresConfig
from repositories.gym_repository import GymRepository
from repositories.billing_repository import BillingRepository
from repositories.access_repository import AccessRepository, AccessDenied, ResourceNotFound
from services.gym_service import GymService, CatalogueChanged, DEFAULT_CONFIG, clean_image
from services.billing_service import BillingService
from billing_fixtures import config as billing_config


@unittest.skipUnless(foundations.ENABLED, 'Set VECTRA_RUN_MIGRATION_TESTS=1')
class GymOnboardingTests(foundations.DisposablePostgresTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.create_database('gym'); cls.flyway('gym', 'migrate'); cls.flyway('gym', 'validate')
        cls.config = PostgresConfig(host='127.0.0.1', port=cls.port, dbname='gym', user='postgres', password=cls.password, sslmode='disable')

    def setUp(self):
        self.repo = GymRepository(self.config)
        self.billing = BillingService(BillingRepository(self.config), billing_config())
        self.service = GymService(self.repo, self.billing)
        self.url = patch('services.gym_service.public_web_url', return_value='https://fixture.invalid')
        self.url.start(); self.addCleanup(self.url.stop)
        with self.repo.transaction() as db:
            self.owner = self.new_user(db)
            self.member = self.new_user(db)
            self.trainer = self.new_user(db)
            self.admin = self.new_user(db)
            self.org = db.execute("INSERT INTO organizations(name,organization_type,billing_required) VALUES('Fixture Gym','gym',false) RETURNING id").fetchone()['id']
            self.owner_rel = self.role(db, self.owner, 'owner')
            self.trainer_rel = self.role(db, self.trainer, 'trainer')
            self.role(db, self.admin, 'admin')
        self.cfg = copy.deepcopy(DEFAULT_CONFIG)
        self.cfg.update(display_name='Fixture Gym', registration_enabled=True, plans=[{'id': str(uuid4()), 'kind': 'gym', 'name': 'Quarterly', 'terms': 'Three months, manual renewal.', 'amount_paise': 12345, 'duration_months': 3, 'sessions': None, 'active': True, 'trainer_relationship_id': None, 'trainer_name': ''}])
        with self.access(self.owner) as access:
            self.asset = self.service.upload(access, 'payment_qr', self.png())['id']
            self.cfg['payment'] = {'recipient_name': 'Fixture Merchant', 'upi_id': 'fixture@bank', 'qr_asset_id': str(self.asset)}
            self.saved = self.service.save(access, 0, self.cfg, True)
        self.public_id = self.saved['public_id']

    def new_user(self, db):
        return db.execute("INSERT INTO users(email,password_hash,created_at,updated_at,verification_required,email_verified_at) VALUES(%s,'fixture',now(),now(),false,now()) RETURNING *", (uuid4().hex + '@example.invalid',)).fetchone()

    def role(self, db, user, role):
        rel = self.repo.ensure_relationship(db, (self.org, user['id']))['id']
        db.execute('INSERT INTO organization_staff_roles(organization_id,relationship_id,role) VALUES(%s,%s,%s)', (self.org, rel, role))
        return rel

    @staticmethod
    def png():
        output = BytesIO(); Image.new('RGB', (200, 200), 'white').save(output, 'PNG'); return output.getvalue()

    @contextmanager
    def access(self, user, member=False):
        with self.repo.transaction() as db:
            yield AccessRepository(db, self.org, user['id'], member_mode=member)

    def payload(self, **changes):
        return {'request_id': uuid4(), 'revision': 1, 'plan_ids': [self.cfg['plans'][0]['id']], 'member_name': 'Fixture Member', 'mobile': '+91 9876543210', 'accept_terms': True, 'replaces_id': None, **changes}

    def join(self, payload=None, user=None):
        return self.service.join(self.public_id, user or self.member, payload or self.payload())

    def test_public_allowlist_and_two_gym_destinations_are_isolated(self):
        public = self.service.public(self.public_id)
        self.assertTrue(public['available']); self.assertNotIn('trainers', public)
        self.assertNotIn('organization_id', public); self.assertNotIn('trainer_relationship_id', public['plans'][0])
        with self.repo.transaction() as db:
            other = db.execute("INSERT INTO organizations(name,organization_type,billing_required) VALUES('Second','gym',false) RETURNING id").fetchone()['id']
            self.repo.ensure_profile(db, other)
            cfg = copy.deepcopy(self.cfg); cfg['payment']['recipient_name'] = 'Second Recipient'; cfg['payment']['upi_id'] = 'second@bank'; cfg['plans'][0]['amount_paise'] = 99000
            self.repo.save_profile(db, other, self.owner['id'], 1, cfg)
            second = self.repo.profile(db, other)['public_id']
        self.assertNotEqual(second, self.public_id)
        self.assertEqual(self.service.public(second)['payment']['upi_id'], 'second@bank')
        self.assertEqual(self.service.public(self.public_id)['plans'][0]['amount_paise'], 12345)

    def test_join_is_atomic_idempotent_and_creates_no_coach_role_or_assignment(self):
        payload = self.payload()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.join(payload), range(2)))
        self.assertEqual(results[0]['id'], results[1]['id'])
        self.assertEqual(results[0]['amount_paise'], 12345)
        self.assertEqual(results[0]['status'], 'pending')
        with self.repo.transaction() as db:
            rel = db.execute('SELECT id FROM organization_relationships WHERE organization_id=%s AND user_id=%s', (self.org, self.member['id'])).fetchone()['id']
            self.assertEqual(db.execute('SELECT count(*) AS n FROM organization_staff_roles WHERE relationship_id=%s', (rel,)).fetchone()['n'], 0)
            self.assertEqual(db.execute('SELECT count(*) AS n FROM clients WHERE organization_relationship_id=%s', (rel,)).fetchone()['n'], 0)
            self.assertEqual(db.execute('SELECT count(*) AS n FROM coaches WHERE user_id=%s', (self.member['id'],)).fetchone()['n'], 0)
        payload['member_name'] = 'Different'
        with self.assertRaises(ValueError): self.join(payload)

    def test_edit_retains_snapshot_and_refresh_requires_explicit_new_purchase(self):
        original = self.join()
        with self.access(self.owner) as access:
            asset = self.service.upload(access, 'payment_qr', self.png())['id']
            self.cfg['payment'].update(upi_id='new@bank', qr_asset_id=str(asset))
            self.cfg['plans'][0]['amount_paise'] = 20000
            self.service.save(access, 1, self.cfg, True)
        history = self.service.history(self.public_id, self.member)
        self.assertEqual(history[0]['snapshot']['payment']['upi_id'], 'fixture@bank')
        self.assertEqual(history[0]['amount_paise'], 12345); self.assertTrue(history[0]['needs_review'])
        self.assertEqual(self.service.asset(self.asset), clean_image(self.png()))
        with self.assertRaises(CatalogueChanged): self.join()
        replacement = self.join(self.payload(revision=2, replaces_id=original['id']))
        self.assertEqual(replacement['amount_paise'], 20000)
        self.assertEqual(self.service.history(self.public_id, self.member)[1]['status'], 'superseded')
        with self.repo.transaction() as db:
            with self.assertRaises(psycopg.errors.RaiseException):
                db.execute('UPDATE gym_pending_purchases SET amount_paise=1 WHERE id=%s', (original['id'],))

    def test_owner_payment_preview_audit_and_optimistic_conflict(self):
        changed = copy.deepcopy(self.cfg); changed['payment']['upi_id'] = 'new@bank'
        with self.assertRaises(AccessDenied), self.access(self.admin) as access: self.service.save(access, 1, changed, True)
        with self.assertRaises(ValueError), self.access(self.owner) as access: self.service.save(access, 1, changed, False)
        with self.access(self.admin) as access:
            self.cfg['description'] = 'Admin can manage branding'
            saved = self.service.save(access, 1, self.cfg, False)
            self.assertEqual(len(saved['audit']), 2)
        with self.assertRaises(CatalogueChanged), self.access(self.owner) as access: self.service.save(access, 1, self.cfg, True)
        with self.assertRaises(AccessDenied), self.access(self.trainer) as access: self.service.setup(access)
        with self.assertRaises(AccessDenied), self.access(self.owner, member=True) as access: self.service.setup(access)

    def test_inactive_relationship_cannot_be_reactivated_and_unverified_cannot_join(self):
        with self.repo.transaction() as db:
            self.repo.ensure_relationship(db, (self.org, self.member['id']))
            db.execute("UPDATE organization_relationships SET status='inactive' WHERE organization_id=%s AND user_id=%s", (self.org, self.member['id']))
        with self.assertRaises(AccessDenied): self.join()
        with self.assertRaises(AccessDenied): self.join(user={**self.owner, 'verification_required': True})
        self.assertEqual(self.service.history(self.public_id, self.member), [])

    def test_unavailable_unknown_paused_inactive_and_billing_pending(self):
        self.assertEqual(self.service.public(uuid4())['reason'], 'not_found')
        with self.access(self.owner) as access:
            self.cfg['registration_enabled'] = False; self.service.save(access, 1, self.cfg, True)
        self.assertEqual(self.service.public(self.public_id)['reason'], 'paused')
        with self.assertRaises(ValueError): self.join()
        with self.repo.transaction() as db: db.execute("UPDATE organizations SET status='inactive' WHERE id=%s", (self.org,))
        self.assertEqual(self.service.public(self.public_id)['reason'], 'inactive')
        with self.repo.transaction() as db: db.execute("UPDATE organizations SET status='active',billing_required=true WHERE id=%s", (self.org,))
        self.assertEqual(self.service.public(self.public_id)['reason'], 'subscription_unavailable')

    def test_rename_preserves_public_id_and_private_upload_requires_owner(self):
        with self.access(self.owner) as access:
            draft = self.service.upload(access, 'logo', self.png())['id']
            self.assertEqual(self.service.asset(draft, access), clean_image(self.png()))
            self.cfg['display_name'] = 'Renamed Gym'
            saved = self.service.save(access, 1, self.cfg, True)
            self.assertEqual(saved['public_id'], self.public_id)
        with self.assertRaises(ResourceNotFound): self.service.asset(draft)
        with self.assertRaises(AccessDenied), self.access(self.admin) as access: self.service.upload(access, 'payment_qr', self.png())

    def test_foreign_images_trainers_and_purchase_refresh_are_rejected(self):
        with self.repo.transaction() as db:
            other = db.execute("INSERT INTO organizations(name,organization_type,billing_required) VALUES('Other','gym',false) RETURNING id").fetchone()['id']
            self.repo.ensure_profile(db, other)
            asset = uuid4()
            db.execute("INSERT INTO gym_assets(id,organization_id,kind,png,created_by) VALUES(%s,%s,'logo',%s,%s)", (asset, other, self.png(), self.owner['id']))
        invalid = copy.deepcopy(self.cfg); invalid['logo_id'] = str(asset)
        with self.assertRaises(ValueError), self.access(self.owner) as access: self.service.save(access, 1, invalid, True)
        original = self.join(user=self.owner)
        with self.assertRaises(ValueError): self.join(self.payload(replaces_id=original['id']))
        self.assertEqual(self.service.history(self.public_id, self.member), [])
        with self.repo.transaction() as db:
            self.assertIsNone(db.execute('SELECT id FROM organization_relationships WHERE organization_id=%s AND user_id=%s', (self.org, self.member['id'])).fetchone())

    def test_pt_snapshot_scope_duration_and_role_revalidation(self):
        # Step 7 requires actual paid gym coverage before a PT purchase.
        from services.membership_service import MembershipService, today_india
        from repositories.membership_repository import MembershipRepository
        gym_purchase = self.join()
        with self.access(self.owner) as access:
            MembershipService(MembershipRepository(self.config)).act(access, gym_purchase['id'], 'confirm',
                {'note': 'Fixture receipt', 'reference': uuid4().hex, 'method': 'cash',
                 'amount_paise': 12345, 'received_on': str(today_india()), 'receipt_checked': True}, True)
        pt = {**self.cfg['plans'][0], 'id': str(uuid4()), 'kind': 'pt', 'name': 'Trainer plan', 'trainer_name': 'Coach Public', 'trainer_relationship_id': self.trainer_rel}
        self.cfg['plans'].append(pt)
        with self.access(self.owner) as access: self.service.save(access, 1, self.cfg, True)
        plans = [p['id'] for p in self.cfg['plans']]
        result = self.join(self.payload(revision=2, plan_ids=plans))
        self.assertEqual(result['snapshot']['plans'][1]['trainer_relationship_id'], self.trainer_rel)
        with self.repo.transaction() as db:
            db.execute("UPDATE organization_staff_roles SET revoked_at=now() WHERE relationship_id=%s AND role='trainer'", (self.trainer_rel,))
        self.assertEqual(len(self.service.public(self.public_id)['plans']), 1)
        with self.assertRaises(ValueError): self.join(self.payload(revision=2, plan_ids=plans))

    def test_gym_schema_upgrade_from_step4(self):
        self.create_database('gym_upgrade'); self.flyway('gym_upgrade', 'migrate', '-target=8')
        with self.connect('gym_upgrade') as db:
            db.execute("INSERT INTO organizations(name,organization_type) VALUES('Existing gym','gym')")
        self.flyway('gym_upgrade', 'migrate'); self.flyway('gym_upgrade', 'validate')
        with self.connect('gym_upgrade') as db:
            self.assertEqual(db.execute('SELECT name FROM organizations').fetchone()[0], 'Existing gym')
            self.assertEqual(db.execute('SELECT count(*) FROM gym_pending_purchases').fetchone()[0], 0)

    def test_http_public_private_verification_and_billing_boundaries(self):
        import asyncio
        from contextlib import ExitStack
        import importlib.util
        import json
        import secrets
        from unittest.mock import Mock
        from config.auth_config import AuthConfig
        from services.security_service import SecurityService
        from services.auth_service import AuthService
        from services.identity_service import IdentityService
        with ExitStack() as stack:
            stack.enter_context(patch('config.local_settings_loader.load_local_settings'))
            for mod, name in [('auth_service', 'AuthService'), ('client_service', 'ClientService'),
                              ('plan_service', 'PlanService'), ('job_service', 'JobService'),
                              ('job_runner', 'JobRunner'), ('blob_storage_service', 'BlobStorageService'),
                              ('queue_service', 'QueueService'), ('ai_plan_draft_service', 'AiPlanDraftService'),
                              ('pdf_service', 'PdfService'), ('storage_asset_service', 'StorageAssetService')]:
                stack.enter_context(patch(f'services.{mod}.{name}'))
            spec = importlib.util.spec_from_file_location('gym_test_app', foundations.ROOT / 'mobility-ai-service/app.py')
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        security = SecurityService(AuthConfig(secrets.token_urlsafe(32), 24))
        module.auth_service = AuthService(self.repo, security)
        module.identity_service = IdentityService(self.repo, security)
        module.billing_service = self.billing
        module.gym_service = self.service

        def request(path, user=None, method='GET', body=None, org=None):
            async def run():
                messages = []
                raw = json.dumps(body, default=str).encode() if body is not None else b''
                async def receive(): return {'type': 'http.request', 'body': raw, 'more_body': False}
                async def send(message): messages.append(message)
                headers = [(b'content-type', b'application/json'), (b'x-organization-id', str(org or self.org).encode())]
                if user:
                    headers.append((b'authorization', ('Bearer ' + security.create_access_token(user_id=user['id'], email=user['email'])).encode()))
                await module.app({'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'}, 'http_version': '1.1', 'method': method,
                                  'scheme': 'http', 'path': path, 'raw_path': path.encode(), 'query_string': b'', 'root_path': '',
                                  'headers': headers, 'client': ('test', 1), 'server': ('test', 80)}, receive, send)
                status = next(m['status'] for m in messages if m['type'] == 'http.response.start')
                response = b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body')
                return status, response
            return asyncio.run(run())

        public = f'/public/gyms/{self.public_id}'
        self.assertEqual(request(public)[0], 200)
        self.assertEqual(request('/gym/setup')[0], 401)
        self.assertEqual(request('/gym/setup', self.trainer)[0], 403)
        self.assertEqual(request('/gym/setup', self.owner)[0], 200)
        self.assertEqual(request('/gym/setup', self.owner, org=999999)[0], 403)
        payload = self.payload(accept_terms=False)
        self.assertEqual(request(public + '/join', self.member, 'POST', payload)[0], 400)
        payload['accept_terms'] = True
        self.assertEqual(request(public + '/join', method='POST', body=payload)[0], 401)
        self.assertEqual(request(public + '/join', self.member, 'POST', payload)[0], 200)
        self.assertEqual(request('/gym/registrations', self.member)[0], 403)
        status, body = request('/member/gym-registrations', self.member)
        self.assertEqual(status, 200); self.assertEqual(len(json.loads(body)), 1)
        self.assertEqual(json.loads(request(public + '/purchases', self.owner)[1]), [])
        self.assertEqual(request('/gym/registration/qr.png', self.owner)[0], 200)
        self.assertTrue(request('/gym/registration/poster.pdf', self.owner)[1].startswith(b'%PDF'))
        with self.repo.transaction() as db:
            db.execute('UPDATE users SET verification_required=true WHERE id=%s', (self.member['id'],))
        self.assertEqual(request(public + '/join', self.member, 'POST', self.payload())[0], 403)
        changed = copy.deepcopy(self.cfg); changed['payment']['upi_id'] = 'changed@bank'
        self.assertEqual(request('/gym/setup', self.admin, 'PUT', {'revision': 1, 'configuration': changed, 'confirm_payment': True})[0], 403)
        self.assertEqual(request('/gym/setup', self.owner, 'PUT', {'revision': 0, 'configuration': changed, 'confirm_payment': True})[0], 409)
        with self.repo.transaction() as db:
            db.execute("UPDATE organizations SET billing_legacy_until=now()-interval '1 day' WHERE id=%s", (self.org,))
        self.assertEqual(request('/gym/setup', self.owner)[0], 200)
        self.assertEqual(request('/gym/setup', self.owner, 'PUT', {'revision': 1, 'configuration': self.cfg, 'confirm_payment': True})[0], 402)
        self.assertFalse(json.loads(request(public)[1])['available'])
        module.gym_service = Mock()
        self.assertEqual(request('/gym/setup', self.owner, 'PUT', {'revision': 1, 'configuration': self.cfg})[0], 402)
        module.gym_service.save.assert_not_called()

    def test_new_member_verification_and_resend_keep_gym_return_without_entitlements(self):
        import secrets
        from config.auth_config import AuthConfig
        from services.security_service import SecurityService
        from services.identity_service import IdentityService
        identity = IdentityService(self.repo, SecurityService(AuthConfig(secrets.token_urlsafe(32), 24)))
        payload = {'email': uuid4().hex + '@example.invalid', 'password': 'a-test-only-password', 'public_id': self.public_id}
        user = identity.register_member(payload)
        self.assertTrue(user['verification_required'])
        with self.assertRaises(AccessDenied): self.join(user=user)
        with self.repo.transaction() as db:
            action = db.execute("SELECT * FROM identity_actions WHERE user_id=%s AND kind='verify'", (user['id'],)).fetchone()
            self.assertEqual(action['return_gym_public_id'], self.public_id)
            self.assertEqual(db.execute('SELECT count(*) AS n FROM organization_relationships WHERE user_id=%s', (user['id'],)).fetchone()['n'], 0)
            db.execute("UPDATE identity_actions SET created_at=now()-interval '2 minutes' WHERE id=%s", (action['id'],))
        identity.request_email(payload['email'], 'verify')
        with self.repo.transaction() as db:
            actions = db.execute("SELECT * FROM identity_actions WHERE user_id=%s ORDER BY created_at DESC", (user['id'],)).fetchall()
            self.assertEqual(len(actions), 2)
            self.assertEqual(actions[0]['return_gym_public_id'], self.public_id)
        identity.consume(identity.token(actions[0]['id']), 'verify')
        with self.repo.transaction() as db:
            verified = db.execute('SELECT * FROM users WHERE id=%s', (user['id'],)).fetchone()
        self.assertFalse(verified['verification_required'])
        self.assertEqual(self.join(user=verified)['status'], 'pending')
        with self.assertRaises(ValueError): identity.register_member(payload)

    def test_concurrent_replacement_only_supersedes_once(self):
        original = self.join()
        def replace(_):
            try:
                return self.join(self.payload(replaces_id=original['id']))['status']
            except ValueError:
                return 'rejected'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(replace, range(2)))
        self.assertEqual(sorted(results), ['pending', 'rejected'])
        self.assertEqual(len(self.service.history(self.public_id, self.member)), 2)

    def test_pt_cannot_exceed_gym_duration_or_reference_other_gym_trainer(self):
        pt = {**self.cfg['plans'][0], 'id': str(uuid4()), 'kind': 'pt', 'trainer_relationship_id': self.trainer_rel, 'trainer_name': 'Public Coach', 'duration_months': 6}
        self.cfg['plans'].append(pt)
        with self.access(self.owner) as access: self.service.save(access, 1, self.cfg, True)
        with self.assertRaises(ValueError): self.join(self.payload(revision=2, plan_ids=[p['id'] for p in self.cfg['plans']]))
        with self.repo.transaction() as db:
            other = db.execute("INSERT INTO organizations(name,organization_type,billing_required) VALUES('Other','gym',false) RETURNING id").fetchone()['id']
            foreign_rel = self.repo.ensure_relationship(db, (other, self.trainer['id']))['id']
            db.execute("INSERT INTO organization_staff_roles(organization_id,relationship_id,role) VALUES(%s,%s,'trainer')", (other, foreign_rel))
        self.cfg['plans'][1]['trainer_relationship_id'] = foreign_rel
        with self.assertRaises(ValueError), self.access(self.owner) as access: self.service.save(access, 2, self.cfg, True)
