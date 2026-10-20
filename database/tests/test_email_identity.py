"""Step 3 real transactions, migrations, isolation and concurrent consumption."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import secrets
import sys
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

import test_organization_foundations as foundations
sys.path.insert(0, str(foundations.ROOT / 'mobility-ai-service'))
from config.auth_config import AuthConfig
from config.postgres_config import PostgresConfig
from repositories.access_repository import AccessRepository, AccessDenied
from repositories.identity_repository import IdentityRepository
from services.auth_service import AuthService
from services.email_delivery_service import EmailDeliveryService
from services.identity_service import IdentityService
from services.security_service import SecurityService


@unittest.skipUnless(foundations.ENABLED, 'Set VECTRA_RUN_MIGRATION_TESTS=1')
class EmailIdentityDatabaseTests(foundations.DisposablePostgresTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.create_database('email_identity')
        cls.flyway('email_identity', 'migrate')
        cls.config = PostgresConfig(host='127.0.0.1', port=cls.port, dbname='email_identity',
                                   user='postgres', password=cls.password, sslmode='disable')

    def setUp(self):
        self.repo = IdentityRepository(self.config)
        self.security = SecurityService(AuthConfig(secrets.token_urlsafe(32), 24))
        self.service = IdentityService(self.repo, self.security)
        self.email = f'{uuid4().hex}@example.invalid'
        with self.repo.transaction() as db:
            # Prior test deliveries cannot interfere with a new worker fixture.
            db.execute("UPDATE email_outbox SET status='cancelled' WHERE status='pending'")
            self.owner = db.execute("INSERT INTO users(email,password_hash,created_at,updated_at,verification_required) "
                                    "VALUES(%s,'fixture',now(),now(),false) RETURNING *", (self.email,)).fetchone()
            self.org = db.execute("INSERT INTO organizations(name,organization_type,billing_required) VALUES('Gym','gym',false) RETURNING id").fetchone()['id']
            self.rel = db.execute('INSERT INTO organization_relationships(organization_id,user_id) VALUES(%s,%s) RETURNING id',
                                  (self.org, self.owner['id'])).fetchone()['id']
            db.execute("INSERT INTO organization_staff_roles(organization_id,relationship_id,role) VALUES(%s,%s,'owner')", (self.org, self.rel))

    @contextmanager
    def access(self, user=None, org=None):
        with self.repo.transaction() as db:
            yield AccessRepository(db, org or self.org, user or self.owner['id'])

    def action(self, kind='recover', email=None):
        with self.repo.transaction() as db:
            return db.execute('SELECT * FROM identity_actions WHERE email=%s AND kind=%s ORDER BY created_at DESC LIMIT 1',
                              (email or self.email, kind)).fetchone()

    def invite(self, email, role='trainer'):
        with self.access() as access:
            self.service.create_invitation(access, email, role)
        return self.action('invite', email)

    def test_fresh_and_upgrade_preserve_unverified_legacy_access(self):
        self.create_database('email_upgrade')
        self.flyway('email_upgrade', 'migrate', '-target=6')
        with self.connect('email_upgrade') as db:
            db.execute("INSERT INTO users(email,password_hash,created_at,updated_at) VALUES('legacy@example.invalid','fixture',now(),now())")
        self.flyway('email_upgrade', 'migrate')
        self.flyway('email_upgrade', 'validate')
        with self.connect('email_upgrade') as db:
            self.assertEqual(db.execute('SELECT verification_required,email_verified_at,session_version FROM users').fetchone(), (False, None, 0))
            self.assertTrue(db.execute("INSERT INTO users(email,password_hash,created_at,updated_at) VALUES('new@example.invalid','fixture',now(),now()) RETURNING verification_required").fetchone()[0])

    def test_signup_and_outbox_are_atomic_and_verification_single_use(self):
        payload = dict(email=f'{uuid4().hex}@example.invalid', password='long-test-password', coach=dict(first_name='New', last_name='Coach'))
        with patch.object(self.service, 'enqueue', side_effect=RuntimeError('outbox failure')):
            with self.assertRaises(RuntimeError): self.service.register_coach(payload)
        self.assertIsNone(self.repo.fetch_user_by_email(payload['email']))
        user, _ = self.service.register_coach(payload)
        self.assertTrue(user['verification_required'])
        action = self.action('verify', payload['email'])
        token = self.service.token(action['id'])
        self.service.consume(token, 'verify')
        self.assertFalse(self.repo.fetch_user_by_id(user['id'])['verification_required'])
        with self.assertRaises(ValueError): self.service.consume(token, 'verify')

    def test_recovery_is_single_use_concurrently_and_invalidates_sessions(self):
        auth = AuthService(self.repo, self.security)
        token = self.security.create_access_token(user_id=self.owner['id'], email=self.email)
        self.service.request_email(self.email, 'recover')
        action = self.action()
        link = self.service.token(action['id'])
        def consume():
            try:
                self.service.consume(link, 'recover', password='replacement-password')
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(lambda _: consume(), range(2))), [False, True])
        self.assertIsNone(auth.get_authenticated_user(token))
        response = auth.sign_in(email=self.email, password='replacement-password')
        self.assertIsNotNone(auth.get_authenticated_user(response['access_token']))

    def test_request_enumeration_cooldown_and_rate_limit(self):
        known = self.service.request_email(self.email, 'recover')
        self.assertEqual(known, self.service.request_email('unknown@example.invalid', 'recover'))
        self.service.request_email(self.email, 'recover')
        with self.repo.transaction() as db:
            self.assertEqual(db.execute("SELECT count(*) AS n FROM identity_actions WHERE email=%s", (self.email,)).fetchone()['n'], 1)
        key = uuid4().hex
        self.assertTrue(all(self.service.rate_limit(key) for _ in range(20)))
        self.assertFalse(self.service.rate_limit(key))

    def test_new_invitee_gets_only_invited_business_no_coach_business(self):
        email = f'{uuid4().hex}@example.invalid'
        action = self.invite(email)
        self.service.consume(self.service.token(action['id']), 'invite', email=email, password='new-staff-password')
        user = self.repo.fetch_user_by_email(email)
        contexts = self.repo.list_user_organizations(user['id'])
        self.assertEqual([(c['organization_id'], c['staff_roles']) for c in contexts], [(self.org, ['trainer'])])
        self.assertIsNone(self.repo.fetch_coach_by_user_id(user['id']))
        self.assertIsNotNone(user['email_verified_at'])
        with self.assertRaises(ValueError):
            self.service.consume(self.service.token(action['id']), 'invite', email=email, password='new-staff-password')

    def test_existing_invitee_requires_matching_authenticated_account(self):
        action = self.invite(self.email, 'admin')
        token = self.service.token(action['id'])
        for kwargs in ({'email': 'wrong@example.invalid', 'current_user': self.owner},
                       {'email': self.email, 'password': 'cannot-overwrite-password'},
                       {'email': self.email, 'current_user': {'id': -1}}):
            with self.assertRaises(ValueError): self.service.consume(token, 'invite', **kwargs)
        self.service.consume(token, 'invite', email=self.email, current_user=self.owner)
        self.assertEqual(self.repo.fetch_user_by_id(self.owner['id'])['password_hash'], 'fixture')

    def test_expired_revoked_wrong_purpose_and_removed_issuer_fail(self):
        for mode in ('expired', 'revoked', 'purpose', 'issuer'):
            email = f'{uuid4().hex}@example.invalid'
            action = self.invite(email)
            with self.repo.transaction() as db:
                if mode == 'expired':
                    db.execute("UPDATE identity_actions SET created_at=now()-interval '2 days', expires_at=now()-interval '1 day' WHERE id=%s", (action['id'],))
                elif mode == 'revoked':
                    db.execute('UPDATE identity_actions SET revoked_at=now() WHERE id=%s', (action['id'],))
                elif mode == 'issuer':
                    db.execute('UPDATE organization_staff_roles SET revoked_at=now() WHERE relationship_id=%s', (self.rel,))
            with self.assertRaises((ValueError, AccessDenied)):
                self.service.consume(self.service.token(action['id']), 'verify' if mode == 'purpose' else 'invite', email=email, password='new-staff-password')
            self.assertIsNone(self.repo.fetch_user_by_email(email))

    def test_invitation_permissions_and_cross_business_revocation(self):
        email = f'{uuid4().hex}@example.invalid'
        action = self.invite(email)
        with self.repo.transaction() as db:
            db.execute("UPDATE organization_staff_roles SET role='admin' WHERE relationship_id=%s", (self.rel,))
        with self.access() as access:
            with self.assertRaises(AccessDenied): self.service.create_invitation(access, email, 'admin')
            with self.assertRaises(AccessDenied): self.service.create_invitation(access, email, 'owner')
        with self.repo.transaction() as db:
            other_org = db.execute("INSERT INTO organizations(name,organization_type) VALUES('Other','gym') RETURNING id").fetchone()['id']
            rel = db.execute('INSERT INTO organization_relationships(organization_id,user_id) VALUES(%s,%s) RETURNING id', (other_org, self.owner['id'])).fetchone()['id']
            db.execute("INSERT INTO organization_staff_roles(organization_id,relationship_id,role) VALUES(%s,%s,'owner')", (other_org, rel))
        with self.access(org=other_org) as access:
            with self.assertRaises(AccessDenied): self.service.revoke_invitation(access, action['id'])
        with self.repo.transaction() as db:
            db.execute("UPDATE organization_staff_roles SET role='trainer' WHERE relationship_id=%s", (self.rel,))
        with self.access() as access:
            with self.assertRaises(AccessDenied): self.service.create_invitation(access, email, 'trainer')

    def test_concurrent_workers_send_once_and_retry_failure(self):
        self.service.request_email(self.email, 'verify')
        adapter = Mock()
        worker = EmailDeliveryService(self.repo, self.service, adapter, 'https://example.invalid')
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(lambda _: worker.process_one(), range(2))), [False, True])
        adapter.send.assert_called_once()
        self.service.request_email(self.email, 'recover')
        adapter.send.side_effect = RuntimeError('secret provider error')
        self.assertTrue(worker.process_one())
        with self.repo.transaction() as db:
            row = db.execute("SELECT e.* FROM email_outbox e JOIN identity_actions a ON a.id=e.action_id WHERE a.email=%s AND a.kind='recover'", (self.email,)).fetchone()
            self.assertEqual((row['status'], row['attempts'], row['error_code']), ('pending', 1, 'provider_send_failed'))
            db.execute('UPDATE email_outbox SET available_at=now() WHERE id=%s', (row['id'],))
        adapter.send.side_effect = None
        self.assertTrue(worker.process_one())
        self.assertFalse(worker.process_one())

    def test_http_signup_verification_invitation_and_recovery(self):
        import asyncio
        import json
        sys.path.insert(0, str(foundations.ROOT / 'mobility-ai-service/tests'))
        from test_auth_routes import AuthRouteTests
        AuthRouteTests.setUpClass()
        module = AuthRouteTests.module
        module.auth_service = AuthService(self.repo, self.security)
        module.identity_service = self.service

        def request(path, data=None, token=None, method='POST'):
            async def run():
                sent = []
                body = json.dumps(data or {}).encode()
                async def receive():
                    return {'type': 'http.request', 'body': body, 'more_body': False}
                async def send(message): sent.append(message)
                headers = [(b'content-type', b'application/json'), (b'x-organization-id', str(self.org).encode())]
                if token: headers.append((b'authorization', f'Bearer {token}'.encode()))
                await module.app({'type':'http','asgi':{'version':'3.0','spec_version':'2.4'},'http_version':'1.1',
                    'method':method,'scheme':'http','path':path,'raw_path':path.encode(),'query_string':b'',
                    'root_path':'','headers':headers,'client':('email-fixture',1),'server':('test',80)}, receive, send)
                status = next(m['status'] for m in sent if m['type']=='http.response.start')
                return status, json.loads(b''.join(m.get('body',b'') for m in sent if m['type']=='http.response.body'))
            return asyncio.run(run())

        email = f'{uuid4().hex}@example.invalid'
        status, signup = request('/auth/signup', {'email':email,'password':'long-new-password','coach':{'first_name':'Test','last_name':'Coach'}})
        self.assertEqual(status, 200)
        self.assertTrue(signup['user']['verification_required'])
        self.assertEqual(request('/clients', token=signup['access_token'], method='GET')[0], 403)
        action = self.action('verify', email)
        self.assertEqual(request('/auth/email/verify/confirm', {'token':self.service.token(action['id'])})[0], 200)
        self.assertFalse(request('/auth/me', token=signup['access_token'], method='GET')[1]['user']['verification_required'])
        owner_token = self.security.create_access_token(user_id=self.owner['id'], email=self.email)
        invited_email = f'{uuid4().hex}@example.invalid'
        self.assertEqual(request('/organization/invitations', {'email':invited_email,'role':'trainer'}, owner_token)[0], 200)
        status, invitations = request('/organization/invitations', token=owner_token, method='GET')
        self.assertEqual(status, 200)
        self.assertNotIn('token_hash', invitations[0])
        invite = self.action('invite', invited_email)
        self.assertEqual(request('/auth/email/invite/confirm', {'email':invited_email,'password':'invited-password','token':self.service.token(invite['id'])})[0], 200)
        status, signed = request('/auth/signin', {'email':invited_email,'password':'invited-password'})
        self.assertEqual(status, 200)
        self.assertEqual(signed['organizations'][0]['staff_roles'], ['trainer'])
        self.assertEqual(request('/organization/invitations', {'email':'forged@example.invalid','role':'trainer'}, signed['access_token'])[0], 403)
        self.assertEqual(request('/auth/email/recover/request', {'email':invited_email})[0], 200)
        recovery = self.action('recover', invited_email)
        self.assertEqual(request('/auth/email/recover/confirm', {'token':self.service.token(recovery['id']), 'password':'replacement-password'})[0], 200)
        self.assertEqual(request('/auth/me', token=signed['access_token'], method='GET')[0], 401)

    def test_concurrent_invitation_acceptance_grants_once(self):
        email = f'{uuid4().hex}@example.invalid'
        action = self.invite(email)
        def accept(_):
            try:
                self.service.consume(self.service.token(action['id']), 'invite', email=email, password='invited-password')
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(accept, range(2))), [False, True])
        user = self.repo.fetch_user_by_email(email)
        self.assertEqual(self.repo.list_user_organizations(user['id'])[0]['staff_roles'], ['trainer'])
