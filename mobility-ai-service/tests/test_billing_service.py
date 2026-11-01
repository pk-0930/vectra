from copy import deepcopy
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import unittest
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

from billing_fixtures import PLAN, FakeRazorpay, config
from config.billing_config import get_billing_config
from services.billing_service import BillingService, access_state
from services.razorpay_service import ProviderError, RazorpayService, verify_signature
from repositories.access_repository import AccessDenied
from repositories.billing_repository import BillingRepository


class BillingServiceTests(unittest.TestCase):
    def test_owner_cannot_create_a_second_active_gym_but_idempotent_retry_returns_existing(self):
        repository = BillingRepository(Mock())
        db = Mock()
        request_row = {'name': 'Gym', 'business_type': 'gym', 'organization_id': 7}
        def execute(sql, *args):
            if 'SELECT * FROM business_onboarding_requests' in sql:
                return Mock(fetchone=Mock(return_value=None))
            if "o.organization_type='gym'" in sql:
                return Mock(fetchone=Mock(return_value={'exists': 1}))
            return Mock()
        db.execute.side_effect = execute
        with self.assertRaisesRegex(ValueError, 'only one active gym'):
            repository.create_business(db, 3, 'request-1', 'Another Gym', 'gym')
        self.assertEqual(db.execute.call_count, 4)
        self.assertIn('pg_advisory_xact_lock', str(db.execute.call_args_list[2]))

        db = Mock()
        db.execute.side_effect = lambda sql, *args: Mock(fetchone=Mock(return_value=request_row)) if 'SELECT * FROM business_onboarding_requests' in sql else Mock()
        self.assertEqual(repository.create_business(db, 3, 'request-1', 'Gym', 'gym'), 7)
        self.assertEqual(db.execute.call_count, 2)

    def test_admin_billing_summary_exposes_access_state_without_financial_details(self):
        repository = MagicMock()
        repository.transaction.return_value.__enter__.return_value = object()
        repository.authorize.return_value.roles = {'admin'}
        repository.organization.return_value = {'name': 'Gym', 'organization_type': 'gym', 'billing_required': False, 'billing_legacy_until': None}
        repository.payments.return_value = []
        result = BillingService(repository, config(), self.provider).summary({'id': 4}, 9)
        self.assertIn('access', result)
        self.assertFalse(result['owner'])
        self.assertNotIn('payments', result)
        self.assertNotIn('subscription', result)
        self.assertNotIn('plans', result)

    def setUp(self):
        self.config = config()
        self.provider = FakeRazorpay()
        self.service = BillingService(Mock(), self.config, self.provider)
        self.row = dict(id=uuid4(),organization_id=1,provider_id=None,plan_snapshot={**PLAN,'grace_days':7},start_at=None)
        self.remote = self.provider.create(self.row)
        self.invoice, self.payment = self.provider.charge(self.remote['id'])
        self.organization = {'billing_required':True,'billing_legacy_until':None}

    def test_paid_invoice_checks_amount_currency_plan_invoice_and_capture(self):
        result = self.service.verified_payment(self.row,self.remote,self.invoice,self.payment)
        self.assertEqual(result['amount_paise'],10000)
        for field,value in [('amount',9999),('currency','USD'),('status','authorized'),('captured',False),('invoice_id','inv_other')]:
            with self.subTest(field=field), self.assertRaises(ProviderError):
                self.service.verified_payment(self.row,self.remote,self.invoice,{**self.payment,field:value})
        for field,value in [('subscription_id','sub_other'),('amount_paid',1),('amount_due',1),('billing_end',1)]:
            with self.subTest(field=field), self.assertRaises(ProviderError):
                self.service.verified_payment(self.row,self.remote,{**self.invoice,field:value},self.payment)

    def test_subscription_and_catalogue_must_match_local_snapshot(self):
        self.service.validate_plan(PLAN,self.provider.plan('plan_fixture'))
        for field,value in [('plan_id','plan_other'),('quantity',2),('total_count',100),('notes',{})]:
            with self.assertRaises(ProviderError): self.service.validate_subscription(self.row,{**self.remote,field:value})
        self.provider.plan_mismatch=True
        with self.assertRaises(ProviderError): self.service.validate_plan(PLAN,self.provider.plan('plan_fixture'))

    def test_paid_coverage_grace_expiry_future_gap_and_refunds(self):
        p=self.service.verified_payment(self.row,self.remote,self.invoice,self.payment)
        p['plan_snapshot']={'grace_days':7}
        self.assertEqual(access_state(self.organization,[p],p['period_start'])['access'],'active')
        self.assertEqual(access_state(self.organization,[p],p['period_end'])['access'],'grace')
        self.assertEqual(access_state(self.organization,[p],p['period_end']+timedelta(days=7))['access'],'read_only')
        self.assertEqual(access_state(self.organization,[p],p['period_start']-timedelta(seconds=1))['access'],'read_only')
        p['refunded_paise']=p['amount_paise']
        self.assertEqual(access_state(self.organization,[p])['access'],'read_only')
        p['refunded_paise']=1
        self.assertEqual(access_state(self.organization,[p])['access'],'active')
        self.assertEqual(access_state(self.organization,[])['access'],'pending')

    def test_legacy_access_and_deadline_are_explicit(self):
        org={'billing_required':False,'billing_legacy_until':None}
        self.assertEqual(access_state(org,[])['access'],'legacy')
        org['billing_legacy_until']=datetime.now(UTC)-timedelta(seconds=1)
        self.assertEqual(access_state(org,[])['access'],'read_only')

    def test_webhook_signature_raw_body_and_event_allowlist(self):
        raw=json.dumps({'event':'subscription.charged','payload':{'subscription':{'entity':{'id':'sub_fixture'}}}}).encode()
        sig=hmac.new(self.config.webhook_secret.encode(),raw,hashlib.sha256).hexdigest()
        self.service.webhook(raw,sig,'event-1')
        self.service.repository.record_webhook.assert_called_once()
        for invalid in ('bad',sig+'0','é'*64):
            with self.assertRaises(AccessDenied): self.service.webhook(raw,invalid,'event-1')
        self.assertFalse(verify_signature(raw+b' ',sig,self.config.webhook_secret))

    def test_config_has_no_invented_prices_and_rejects_mode_mismatch(self):
        with patch.dict('os.environ',{},clear=True):
            self.assertEqual(get_billing_config().plans,())
            self.assertFalse(get_billing_config().enabled)
        with patch.dict('os.environ',{'RAZORPAY_MODE':'live','RAZORPAY_KEY_ID':'rzp_test_wrong'},clear=True):
            with self.assertRaises(ValueError): get_billing_config()
        with patch.dict('os.environ',{'SOFTWARE_PLANS_JSON':json.dumps([{**PLAN,'amount_paise':0}])},clear=True):
            with self.assertRaises(ValueError): get_billing_config()

    def test_local_access_requires_explicit_local_environment_and_disables_checkout(self):
        with patch.dict('os.environ',{},clear=True):
            config = get_billing_config()
            self.assertEqual(config.environment, 'production')
            self.assertFalse(config.local_access)
        with patch.dict('os.environ',{'APP_ENVIRONMENT':'local','SOFTWARE_BILLING_LOCAL_ACCESS':'true',
                                      'RAZORPAY_KEY_ID':'rzp_test_local','RAZORPAY_KEY_SECRET':'secret',
                                      'RAZORPAY_WEBHOOK_SECRET':'webhook','SOFTWARE_PLANS_JSON':json.dumps([PLAN])},clear=True):
            config = get_billing_config()
            self.assertTrue(config.local_access)
            self.assertFalse(config.enabled)
            service = BillingService(Mock(), config, self.provider)
            self.assertEqual(service.state(None, 1)['access'], 'legacy')
            repository = MagicMock()
            repository.transaction.return_value.__enter__.return_value = object()
            repository.authorize.return_value.roles = {'owner'}
            repository.organization.return_value = {'name':'Local gym','organization_type':'gym'}
            repository.payments.return_value = []
            repository.subscriptions.return_value = []
            summary = BillingService(repository, config, self.provider).summary({'id':1}, 1)
            self.assertEqual(summary['mode'], 'local')
            self.assertTrue(summary['local_access'])
            self.assertEqual(summary['access'], 'legacy')
            self.assertFalse(summary['checkout_available'])
            repository.upsert_payment.assert_not_called()
            repository.insert_subscription.assert_not_called()
        for environment in ('staging', 'production'):
            with self.subTest(environment=environment), patch.dict('os.environ',{
                    'APP_ENVIRONMENT':environment,'SOFTWARE_BILLING_LOCAL_ACCESS':'true'},clear=True):
                with self.assertRaises(ValueError): get_billing_config()

    def test_provider_errors_are_sanitized_and_creation_not_automatically_retried(self):
        session=Mock()
        session.request.return_value.status_code=500
        session.request.return_value.text='private payment details'
        adapter=RazorpayService(self.config,session)
        with self.assertRaises(ProviderError) as error: adapter.create(self.row)
        self.assertNotIn('private',str(error.exception))
        self.assertEqual(session.request.call_count,1)
        with self.assertRaises(ProviderError): adapter.subscription('../payments')

    def test_duplicate_invoice_cannot_be_a_different_period(self):
        invalid=deepcopy(self.invoice)
        invalid['billing_end']=invalid['billing_start']+60
        with self.assertRaises(ProviderError):self.service.verified_payment(self.row,self.remote,invalid,self.payment)
