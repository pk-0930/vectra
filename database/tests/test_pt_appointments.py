"""Disposable PostgreSQL acceptance tests for PT and appointment concurrency."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4
import unittest
import test_organization_foundations as foundations
import test_gym_onboarding as onboarding
from config.postgres_config import PostgresConfig
from repositories.access_repository import AccessDenied, ResourceNotFound, AccessRepository
from repositories.membership_repository import MembershipRepository
from repositories.pt_repository import PtRepository
from services.membership_service import MembershipService, today_india
from services.pt_service import PtService, coverage_end


@unittest.skipUnless(foundations.ENABLED, 'Set VECTRA_RUN_MIGRATION_TESTS=1')
class PtTests(foundations.DisposablePostgresTests):
    new_user = onboarding.GymOnboardingTests.new_user
    role = onboarding.GymOnboardingTests.role
    png = staticmethod(onboarding.GymOnboardingTests.png)
    access = onboarding.GymOnboardingTests.access
    payload = onboarding.GymOnboardingTests.payload
    join = onboarding.GymOnboardingTests.join

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.create_database('pt')
        cls.flyway('pt', 'migrate'); cls.flyway('pt', 'validate')
        cls.config = PostgresConfig(host='127.0.0.1', port=cls.port, dbname='pt', user='postgres', password=cls.password, sslmode='disable')

    def setUp(self):
        onboarding.GymOnboardingTests.setUp(self)
        self.memberships = MembershipService(MembershipRepository(self.config))
        self.pt = PtService(PtRepository(self.config))
        self.pay(self.join())
        self.duration = {**self.cfg['plans'][0], 'id': str(uuid4()), 'name': 'Monthly PT', 'kind': 'pt', 'duration_months': 1, 'trainer_relationship_id': self.trainer_rel, 'trainer_name': 'Fixture trainer'}
        self.session = {**self.duration, 'id': str(uuid4()), 'name': 'One PT session', 'duration_months': None, 'sessions': 1}
        self.cfg['plans'] += [self.duration, self.session]
        with self.access(self.owner) as access:
            self.service.save(access, 1, self.cfg, True)

    def pay(self, purchase, **overrides):
        with self.access(self.owner) as access:
            return self.memberships.act(access, purchase['id'], 'confirm', {'note': 'Fixture receipt checked', 'reference': uuid4().hex, 'method': 'cash', 'amount_paise': purchase['amount_paise'], 'received_on': str(today_india()), 'receipt_checked': True, **overrides}, True)

    def pt_purchase(self, user=None, single=False):
        return self.join(self.payload(revision=2, plan_ids=[(self.session if single else self.duration)['id']]), user=user)

    def paid_member(self):
        with self.repo.transaction() as db:
            user = self.new_user(db)
        self.pay(self.join(self.payload(revision=2), user=user))
        return user

    def book(self, purchase, user=None, when=None, request_id=None):
        with self.access(user or self.member, member=not bool(user)) as access:
            return self.pt.book(access, {'request_id': request_id or uuid4(), 'entitlement_id': purchase['id'], 'starts_at': (when or datetime.now(timezone.utc)+timedelta(days=1)).isoformat()})

    def test_paid_coverage_required_at_checkout_and_delayed_verification(self):
        with self.repo.transaction() as db:
            unpaid = self.new_user(db)
        with self.assertRaises(ValueError): self.pt_purchase(unpaid)
        purchase = self.pt_purchase()
        with self.repo.transaction() as db:
            db.execute('UPDATE gym_membership_periods SET revoked_at=now() WHERE organization_id=%s', (self.org,))
        result = self.pay(purchase)
        self.assertIn('resolution_error', result)
        self.assertIsNone(result['payment']); self.assertIsNone(result['pt'])
        self.assertEqual(result['purchase']['status'], 'pending')
        self.assertIsNotNone(result['pt_state']['resolution_reason'])

    def test_concurrent_last_slot_and_distinct_member_count(self):
        for _ in range(9): self.pt_purchase(self.paid_member())
        members = [self.paid_member(), self.paid_member()]
        def attempt(user):
            try: return self.pt_purchase(user)['id']
            except ValueError: return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, members))
        self.assertEqual(sum(r is not None for r in results), 1)
        winner = members[0] if results[0] else members[1]
        self.pt_purchase(winner, single=True)
        with self.repo.transaction() as db:
            self.assertEqual(len(self.pt.repository.capacity_members(db, self.org, self.trainer_rel)), 10)

    def test_expired_reservation_and_consented_reassignment_resolution(self):
        purchase = self.pt_purchase()
        with self.repo.transaction() as db:
            db.execute("UPDATE pt_purchase_states SET reserved_until=now()-interval '1 second' WHERE purchase_id=%s", (purchase['id'],))
        for _ in range(10): self.pt_purchase(self.paid_member())
        self.assertIn('resolution_error', self.pay(purchase))
        with self.assertRaises(ValueError), self.access(self.owner) as access:
            self.pt.reassign(access, purchase['id'], self.owner_rel, False, 'Not consented')
        with self.access(self.owner) as access:
            self.pt.reassign(access, purchase['id'], self.owner_rel, True, 'Member agreed to owner coaching')
        result = self.pay(purchase)
        self.assertEqual(result['pt']['trainer_relationship_id'], self.owner_rel)
        self.assertEqual(result['purchase']['snapshot']['plans'][0]['trainer_relationship_id'], self.trainer_rel)

    def test_single_session_booking_cancel_reschedule_and_complete_once(self):
        purchase = self.pt_purchase(single=True); self.pay(purchase)
        when = datetime.now(timezone.utc)+timedelta(days=1)
        request = uuid4()
        appointment = self.book(purchase, when=when, request_id=request)
        self.assertEqual(self.book(purchase, when=when, request_id=request)['id'], appointment['id'])
        with self.assertRaises(ValueError): self.book(purchase, when=when+timedelta(days=1))
        with self.access(self.member, member=True) as access:
            changed = self.pt.change_appointment(access, appointment['id'], 'reschedule', 1, (when+timedelta(hours=2)).isoformat())
            cancelled = self.pt.change_appointment(access, appointment['id'], 'cancel', changed['version'])
            self.assertEqual(cancelled['status'], 'cancelled')
        appointment = self.book(purchase, when=when)
        with self.assertRaises(AccessDenied), self.access(self.member, member=True) as access:
            self.pt.change_appointment(access, appointment['id'], 'complete', 1)
        class AfterSession(datetime):
            @classmethod
            def now(cls, tz=None): return when+timedelta(hours=2)
        def complete(_):
            with self.access(self.trainer) as access:
                return self.pt.change_appointment(access, appointment['id'], 'complete', 1)
        with patch('services.pt_service.datetime', AfterSession), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(complete, range(2)))
        self.assertTrue(all(r['status'] == 'completed' for r in results))
        with self.repo.transaction() as db:
            self.assertEqual(db.execute('SELECT remaining_sessions FROM pt_entitlements WHERE purchase_id=%s', (purchase['id'],)).fetchone()['remaining_sessions'], 0)
            self.assertEqual(db.execute("SELECT count(*) AS n FROM pt_audit WHERE appointment_id=%s AND action='complete'", (appointment['id'],)).fetchone()['n'], 1)

    def test_overlap_duration_daily_limit_and_gym_expiry(self):
        first = self.pt_purchase(); self.pay(first)
        other = self.paid_member(); second = self.pt_purchase(other); self.pay(second)
        when = datetime.now(timezone.utc)+timedelta(days=1)
        self.book(first, when=when)
        with self.assertRaises(ValueError): self.book(second, user=other, when=when+timedelta(minutes=30))
        with self.assertRaises(ValueError): self.book(first, when=when+timedelta(hours=3))
        with self.assertRaises(ValueError): self.book(first, when=when+timedelta(days=100))
        with self.repo.transaction() as db:
            db.execute('UPDATE gym_membership_periods SET revoked_at=now() WHERE organization_id=%s AND relationship_id=(SELECT id FROM organization_relationships WHERE organization_id=%s AND user_id=%s)', (self.org, self.org, self.member['id']))
        with self.assertRaises(ValueError): self.book(first, when=when+timedelta(days=2))

    def test_trainer_removal_reassignment_queue_and_tenant_privacy(self):
        purchase = self.pt_purchase(); result = self.pay(purchase)
        appointment = self.book(purchase)
        with self.access(self.trainer) as access:
            self.assertEqual(len(self.pt.list(access)['entitlements']), 1)
        with self.access(self.owner) as access:
            access.revoke_role(self.trainer_rel, 'trainer')
        with self.access(self.owner) as access:
            self.assertTrue(self.pt.list(access)['entitlements'][0]['needs_reassignment'])
            self.pt.reassign(access, purchase['id'], self.owner_rel, True, 'Member consented')
        with self.access(self.trainer) as access:
            self.assertEqual(self.pt.list(access)['entitlements'], [])
            with self.assertRaises(ResourceNotFound): self.pt.change_appointment(access, appointment['id'], 'cancel', 1)
        with self.repo.transaction() as db:
            self.assertEqual(db.execute('SELECT status FROM coaching_appointments WHERE id=%s', (appointment['id'],)).fetchone()['status'], 'cancelled')
            self.assertIsNotNone(db.execute('SELECT ended_at FROM trainer_client_assignments WHERE organization_id=%s AND trainer_relationship_id=%s AND client_id=%s', (self.org, self.trainer_rel, result['pt']['client_id'])).fetchone()['ended_at'])
        outsider = self.paid_member()
        with self.assertRaises(ResourceNotFound): self.book(purchase, user=outsider)
        with self.access(self.owner, member=True) as access:
            with self.assertRaises(AccessDenied): self.pt.reassign(access, purchase['id'], self.owner_rel, True, 'x')

    def test_confirmation_rolls_back_entitlement_assignment_and_payment(self):
        purchase = self.pt_purchase()
        with patch.object(self.memberships.repository, 'notice', side_effect=RuntimeError('fixture')):
            with self.assertRaises(RuntimeError): self.pay(purchase)
        with self.repo.transaction() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM pt_entitlements WHERE purchase_id=%s', (purchase['id'],)).fetchone())
            self.assertIsNone(db.execute('SELECT 1 FROM gym_verified_payments WHERE purchase_id=%s', (purchase['id'],)).fetchone())

    def test_contiguous_coverage_combines_periods_but_not_gaps(self):
        today = today_india()
        periods = [{'starts_on': today, 'ends_before': today+timedelta(days=10)}, {'starts_on': today+timedelta(days=10), 'ends_before': today+timedelta(days=40)}]
        self.assertEqual(coverage_end(periods, today), today+timedelta(days=40))
        periods[1]['starts_on'] += timedelta(days=1)
        self.assertEqual(coverage_end(periods, today), today+timedelta(days=10))

    def test_online_coaching_has_no_gym_membership_or_capacity_gate(self):
        with self.repo.transaction() as db:
            org = db.execute("INSERT INTO organizations(name,organization_type,billing_required) VALUES('Online Fixture','coaching',false) RETURNING id").fetchone()['id']
            rel = self.repo.ensure_relationship(db, (org, self.owner['id']))['id']
            db.execute("INSERT INTO organization_staff_roles(organization_id,relationship_id,role) VALUES(%s,%s,'owner')", (org, rel))
            access = AccessRepository(db, org, self.owner['id'])
            coach = access.staff_coach_id()
            for index in range(11):
                client = db.execute("INSERT INTO clients(coach_id,organization_id,first_name,last_name,created_at,updated_at) VALUES(%s,%s,'Online','Fixture',now(),now()) RETURNING id", (coach, org)).fetchone()['id']
                access.assign_trainer(client, rel, True)
                result = self.pt.book(access, {'request_id': uuid4(), 'client_id': client, 'trainer_relationship_id': rel, 'starts_at': (datetime.now(timezone.utc)+timedelta(days=1,hours=index)).isoformat()})
                self.assertIsNone(result['entitlement_id'])
            self.assertEqual(len(self.pt.list(access)['appointments']), 11)

    def test_http_pt_booking_privacy_and_reassignment_route(self):
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
        module.pt_service = self.pt

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

        purchase = self.pt_purchase(single=True)
        self.pay(purchase)
        self.assertEqual(request('/pt/workspace')[0], 401)
        result = json.loads(request('/pt/workspace', self.trainer)[1])
        self.assertEqual(len(result['entitlements']), 1)
        self.assertNotIn('payment', result)
        self.assertNotIn('amount_paise', result['entitlements'][0])
        self.assertEqual(request('/pt/workspace', self.owner, org=999999)[0], 403)
        payload = {'request_id': str(uuid4()), 'entitlement_id': str(purchase['id']), 'starts_at': (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
        self.assertEqual(request('/appointments', self.member, 'POST', payload)[0], 200)
        self.assertEqual(request('/appointments', self.member, 'POST', {**payload, 'starts_at': '2026-10-30T10:00:00'})[0], 400)
        path = f'/gym/purchases/{purchase["id"]}/reassign-pt'
        reassignment = {'trainer_relationship_id': self.owner_rel, 'member_consent': True, 'note': 'Consented fixture reassignment'}
        self.assertEqual(request(path, self.trainer, 'POST', reassignment)[0], 403)
        self.assertEqual(request(path, self.owner, 'POST', reassignment)[0], 200)
        self.assertEqual(json.loads(request('/pt/workspace', self.trainer)[1])['entitlements'], [])

    def test_legacy_pt_terms_require_recorded_consent(self):
        current = self.pt_purchase()
        with self.repo.transaction() as db:
            import copy
            snapshot = copy.deepcopy(current['snapshot'])
            del snapshot['pt_service_terms']
            relationship = db.execute('SELECT id FROM organization_relationships WHERE organization_id=%s AND user_id=%s', (self.org, self.member['id'])).fetchone()['id']
            legacy = self.repo.insert_purchase(db, self.org, relationship, uuid4(), 'legacy-fixture', 2, snapshot, current['amount_paise'], None)
        self.assertIn('resolution_error', self.pay(legacy))
        self.assertIsNotNone(self.pay(legacy, pt_terms_consent=True)['pt'])

    def test_unfulfilled_payment_can_be_recorded_as_external_refund(self):
        purchase = self.pt_purchase()
        with self.repo.transaction() as db:
            db.execute('UPDATE gym_membership_periods SET revoked_at=now() WHERE organization_id=%s', (self.org,))
        self.assertIn('resolution_error', self.pay(purchase))
        with self.access(self.owner) as access:
            result = self.memberships.act(access, purchase['id'], 'refund', {'note': 'Receipt returned externally after failed eligibility', 'reference': 'EXTERNAL-REFUND', 'amount_paise': purchase['amount_paise'], 'external_refund_completed': True, 'entitlement': 'revoke'}, True)
        self.assertEqual(result['purchase']['status'], 'refunded')
        self.assertIsNone(result['pt'])

    def test_role_regrant_does_not_resurrect_removed_trainer_work(self):
        purchase = self.pt_purchase(); self.pay(purchase)
        appointment = self.book(purchase)
        with self.access(self.owner) as access: access.revoke_role(self.trainer_rel, 'trainer')
        with self.repo.transaction() as db:
            db.execute("INSERT INTO organization_staff_roles(organization_id,relationship_id,role) VALUES(%s,%s,'trainer')", (self.org, self.trainer_rel))
            self.assertEqual(db.execute('SELECT status FROM coaching_appointments WHERE id=%s', (appointment['id'],)).fetchone()['status'], 'cancelled')
        with self.assertRaises(ValueError): self.book(purchase)
        with self.access(self.owner) as access:
            self.assertTrue(self.pt.list(access)['entitlements'][0]['needs_reassignment'])

    def test_rejection_releases_reservation_and_resubmission_does_not_reacquire(self):
        purchase = self.pt_purchase()
        with self.access(self.owner) as access:
            self.memberships.act(access, purchase['id'], 'reject', {'note': 'Receipt not found'}, True)
        with self.access(self.member, member=True) as access:
            self.memberships.act(access, purchase['id'], 'submit', {'note': 'Corrected reference', 'reference': 'CORRECTED'})
        with self.repo.transaction() as db:
            self.assertEqual(self.pt.repository.capacity_members(db, self.org, self.trainer_rel), set())
