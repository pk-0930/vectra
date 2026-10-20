"""Isolated PostgreSQL payment/entitlement transaction and tenant regression tests."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from unittest.mock import patch
from uuid import uuid4
import test_gym_onboarding as onboarding
import test_organization_foundations as foundations
from config.postgres_config import PostgresConfig
import unittest
from repositories.membership_repository import MembershipRepository
from services.membership_service import MembershipService, today_india, add_months
from repositories.access_repository import AccessDenied, ResourceNotFound


@unittest.skipUnless(foundations.ENABLED, 'Set VECTRA_RUN_MIGRATION_TESTS=1')
class MembershipTests(foundations.DisposablePostgresTests):
    new_user = onboarding.GymOnboardingTests.new_user
    role = onboarding.GymOnboardingTests.role
    png = staticmethod(onboarding.GymOnboardingTests.png)
    access = onboarding.GymOnboardingTests.access
    payload = onboarding.GymOnboardingTests.payload
    join = onboarding.GymOnboardingTests.join

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.create_database('memberships')
        cls.flyway('memberships', 'migrate')
        cls.flyway('memberships', 'validate')
        cls.config = PostgresConfig(host='127.0.0.1', port=cls.port, dbname='memberships', user='postgres', password=cls.password, sslmode='disable')

    def setUp(self):
        onboarding.GymOnboardingTests.setUp(self)
        self.memberships = MembershipService(MembershipRepository(self.config))
        self.purchase = self.join()

    def confirm_payload(self, **changes):
        return {'note': 'Checked fixture merchant receipt', 'reference': uuid4().hex, 'method': 'upi', 'amount_paise': 12345, 'received_on': str(today_india()), 'receipt_checked': True, **changes}

    def act(self, action, payload=None, purchase=None, user=None, admin=True):
        with self.access(user or self.owner) as access:
            return self.memberships.act(access, purchase or self.purchase['id'], action, payload or self.confirm_payload(), admin)

    def test_atomic_concurrent_confirmation_and_reference_reuse(self):
        payload = self.confirm_payload(reference='FIXTURE-REF')
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows = list(pool.map(lambda _: self.act('confirm', payload), range(2)))
        self.assertEqual(rows[0]['membership'], rows[1]['membership'])
        with self.repo.transaction() as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM gym_verified_payments WHERE purchase_id=%s', (self.purchase['id'],)).fetchone()['n'], 1)
            self.assertEqual(db.execute('SELECT count(*) AS n FROM billing_notifications WHERE event_key=%s', (f'membership-confirmed:{self.purchase["id"]}',)).fetchone()['n'], 1)
        other = self.join()
        with self.assertRaises(ValueError): self.act('confirm', payload, other['id'])
        with self.access(self.member) as access:
            self.assertIsNone(self.memberships.details(access, other['id'])['membership'])

    def test_rollback_on_outbox_failure(self):
        with patch.object(self.memberships.repository, 'notice', side_effect=RuntimeError('fixture failure')):
            with self.assertRaises(RuntimeError): self.act('confirm')
        with self.access(self.member) as access:
            detail = self.memberships.details(access, self.purchase['id'])
            self.assertIsNone(detail['membership']); self.assertIsNone(detail['payment'])
            self.assertEqual(detail['purchase']['status'], 'pending'); self.assertEqual(detail['events'], [])

    def test_member_submission_rejection_correction_and_cash(self):
        self.act('submit', {'note': 'Paid owner', 'reference': 'claimed'}, user=self.member, admin=False)
        self.act('reject', {'note': 'No matching receipt'})
        with self.assertRaises(ValueError): self.act('confirm')
        self.act('submit', {'note': 'Corrected reference', 'reference': 'claim-2'}, user=self.member, admin=False)
        result = self.act('confirm', self.confirm_payload(method='cash', reference='CASH-001'))
        self.assertEqual(result['payment']['method'], 'cash')
        result = self.act('correct', {'note': 'Receipt checked at front desk; original record retained'})
        self.assertEqual([e['kind'] for e in result['events']], ['submitted', 'rejected', 'submitted', 'confirmed', 'correction'])
        with self.assertRaises(ValueError): self.act('cancel', {'note': 'Cannot cancel paid history'})

    def test_amount_receipt_and_date_checks(self):
        for changes in [{'amount_paise': 1}, {'receipt_checked': False}, {'method': 'card'}, {'received_on': str(today_india()+timedelta(days=1))}, {'starts_on': str(today_india()-timedelta(days=1))}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.act('confirm', self.confirm_payload(**changes))

    def test_renewals_month_end_leap_year_expiry(self):
        self.assertEqual(add_months(date(2024, 1, 31), 1), date(2024, 2, 29))
        self.assertEqual(add_months(date(2024, 2, 29), 12), date(2025, 2, 28))
        first = self.act('confirm')['membership']
        second = self.act('confirm', purchase=self.join()['id'])['membership']
        self.assertEqual(second['starts_on'], first['ends_before'])
        self.assertEqual(second['ends_before'], add_months(first['ends_before'], 3))
        with patch('services.membership_service.today_india', return_value=second['ends_before']+timedelta(days=10)):
            third = self.act('confirm', self.confirm_payload(received_on=str(today_india())), self.join()['id'])['membership']
        self.assertEqual(third['starts_on'], second['ends_before']+timedelta(days=10))

    def test_tenant_member_trainer_and_member_mode_boundaries(self):
        with self.assertRaises(AccessDenied): self.act('confirm', user=self.trainer)
        with self.assertRaises(AccessDenied): self.act('confirm', user=self.member)
        with self.assertRaises(AccessDenied), self.access(self.owner, member=True) as access:
            self.memberships.act(access, self.purchase['id'], 'confirm', self.confirm_payload(), True)
        foreign = self.join(user=self.owner)
        with self.assertRaises(ResourceNotFound): self.act('submit', {'note': 'x', 'reference': 'x'}, foreign['id'], self.member, False)
        with self.assertRaises(ResourceNotFound): self.act('confirm', purchase=uuid4())
        with self.repo.transaction() as db:
            other = db.execute("INSERT INTO organizations(name,organization_type,billing_required) VALUES('Other','gym',false) RETURNING id").fetchone()['id']
            self.repo.ensure_profile(db, other)
            rel = self.repo.ensure_relationship(db, (other, self.owner['id']))['id']
            db.execute("INSERT INTO organization_staff_roles(organization_id,relationship_id,role) VALUES(%s,%s,'owner')", (other, rel))
        from repositories.access_repository import AccessRepository
        with self.assertRaises(ResourceNotFound), self.repo.transaction() as db:
            self.memberships.act(AccessRepository(db, other, self.owner['id']), self.purchase['id'], 'confirm', self.confirm_payload(), True)

    def test_refund_preserves_payment_and_revokes_only_selected_period(self):
        self.act('confirm')
        renewal = self.act('confirm', purchase=self.join()['id'])['membership']
        result = self.act('refund', {'note': 'Returned externally', 'reference': 'REFUND-1', 'amount_paise': 12345, 'external_refund_completed': True, 'entitlement': 'revoke'})
        self.assertEqual(result['purchase']['status'], 'refunded')
        self.assertEqual(result['membership']['status'], 'revoked')
        self.assertIsNotNone(result['payment'])
        with self.access(self.owner) as access:
            self.assertIsNone(self.memberships.details(access, renewal['purchase_id'], True)['membership']['revoked_at'])
        self.act('refund', {'note': 'Duplicate retry'})
        with self.assertRaises(ValueError): self.act('confirm')

    def test_evidence_is_private_and_does_not_activate(self):
        with self.access(self.member) as access:
            self.memberships.evidence(access, self.purchase['id'], self.png())
            result = self.memberships.details(access, self.purchase['id'])
            self.assertTrue(result['events'][0]['has_evidence']); self.assertIsNone(result['payment'])
        with self.assertRaises(ResourceNotFound), self.access(self.owner) as access:
            self.memberships.evidence(access, self.purchase['id'], self.png())

    def test_reminders_deduplicate_and_renewal_suppresses(self):
        self.act('confirm')
        with self.repo.transaction() as db:
            db.execute('UPDATE gym_membership_periods SET starts_on=%s,ends_before=%s WHERE purchase_id=%s', (today_india()-timedelta(days=30), today_india()+timedelta(days=7), self.purchase['id']))
        self.memberships.reminders(); self.memberships.reminders()
        with self.repo.transaction() as db:
            count = db.execute("SELECT count(*) AS n FROM billing_notifications WHERE event_key LIKE %s", (f'membership-expiry:{self.purchase["id"]}:%',)).fetchone()['n']
            self.assertEqual(count, 1)
        self.act('confirm', purchase=self.join()['id'])
        self.assertEqual(self.memberships.reminders(), 0)


    def test_http_payment_authorization_validation_and_private_evidence(self):
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
        module.membership_service = self.memberships

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

        member_path = f'/member/purchases/{self.purchase["id"]}'
        admin_path = f'/gym/purchases/{self.purchase["id"]}'
        self.assertEqual(request(member_path)[0], 401)
        self.assertEqual(request(admin_path, self.member)[0], 403)
        self.assertEqual(request(admin_path, self.trainer)[0], 403)
        self.assertEqual(request(admin_path, self.owner)[0], 200)
        self.assertEqual(request(member_path, self.member)[0], 200)
        self.assertEqual(request(member_path, self.owner)[0], 404)
        self.assertEqual(request(admin_path, self.owner, org=999999)[0], 403)
        self.assertEqual(request(member_path + '/confirm', self.member, 'POST', self.confirm_payload())[0], 403)
        self.assertEqual(request(admin_path + '/confirm', self.owner, 'POST', self.confirm_payload(amount_paise=True))[0], 422)
        self.assertEqual(request(member_path + '/submit', self.member, 'POST', {'reference': 'FIXTURE-UTR', 'note': 'Paid'})[0], 200)
        with self.access(self.member) as access:
            self.memberships.evidence(access, self.purchase['id'], self.png())
            event = self.memberships.details(access, self.purchase['id'])['events'][-1]
        evidence_path = admin_path + f'/evidence/{event["id"]}'
        self.assertEqual(request(evidence_path, self.trainer)[0], 403)
        status, image = request(evidence_path, self.owner)
        self.assertEqual(status, 200); self.assertTrue(image.startswith(b'\x89PNG'))
        self.assertEqual(request(admin_path + '/confirm', self.admin, 'POST', self.confirm_payload())[0], 200)
        result = json.loads(request(member_path, self.member)[1])
        self.assertEqual(result['purchase']['status'], 'confirmed')
        self.assertEqual(result['membership']['status'], 'active')
        with self.repo.transaction() as db:
            db.execute("UPDATE organizations SET billing_legacy_until=now()-interval '1 day' WHERE id=%s", (self.org,))
        self.assertEqual(request(admin_path + '/correct', self.owner, 'POST', {'note': 'No write in read-only billing'})[0], 402)
        self.assertEqual(request(admin_path, self.owner)[0], 200)

    def test_cancelled_purchase_and_pt_bundle_never_activate(self):
        self.act('cancel', {'note': 'Unpaid cancellation'}, user=self.member, admin=False)
        with self.assertRaises(ValueError): self.act('confirm')
        pt = {**self.cfg['plans'][0], 'id': str(uuid4()), 'kind': 'pt', 'trainer_name': 'Fixture Trainer', 'trainer_relationship_id': self.trainer_rel}
        self.cfg['plans'].append(pt)
        with self.access(self.owner) as access:
            self.service.save(access, 1, self.cfg, True)
        # Step 7 rejects new PT checkout before paid membership exists.
        with self.assertRaises(ValueError):
            self.join(self.payload(revision=2, plan_ids=[p['id'] for p in self.cfg['plans']]))

    def test_payment_history_cannot_be_overwritten_or_deleted(self):
        import psycopg
        self.act('confirm')
        for statement in ['DELETE FROM gym_verified_payments WHERE purchase_id=%s', "UPDATE gym_verified_payments SET reference='REPLACED' WHERE purchase_id=%s", 'DELETE FROM gym_payment_events WHERE purchase_id=%s']:
            with self.assertRaises(psycopg.errors.RaiseException), self.repo.transaction() as db:
                db.execute(statement, (self.purchase['id'],))
