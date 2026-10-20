"""Synthetic provider fixtures only. Never selected by runtime configuration."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from config.billing_config import BillingConfig
from services.razorpay_service import RazorpayService, ProviderError


PLAN = dict(code='gym-monthly', name='Test Gym', business_type='gym', amount_paise=10000,
            period='monthly', interval=1, total_count=12, razorpay_plan_id='plan_fixture')


def config():
    return BillingConfig('test', 'rzp_test_fixture', 'test-key-secret', 'test-webhook-secret',
                         (PLAN, {**PLAN, 'code':'coach-monthly','business_type':'coaching'}), 7, 'software-v1')


class FakeRazorpay:
    provider_id = staticmethod(RazorpayService.provider_id)

    def __init__(self):
        self.remote = {}
        self.invoice_rows = {}
        self.payment_rows = {}
        self.create_calls = 0
        self.cancel_calls = 0
        self.ambiguous_create = False
        self.plan_mismatch = False

    def plan(self, _):
        return {'id':'plan_fixture', 'period':'monthly','interval':1,
                'item':{'amount': 10001 if self.plan_mismatch else 10000,'currency':'INR'}}

    def create(self, row):
        self.create_calls += 1
        provider_id = 'sub_'+uuid4().hex
        value = dict(id=provider_id, plan_id='plan_fixture', quantity=1,total_count=12,status='created',
                     customer_id='cust_fixture', notes={'vectra_attempt':str(row['id']), 'vectra_organization':str(row['organization_id'])})
        self.remote[provider_id] = value
        self.invoice_rows[provider_id] = []
        if self.ambiguous_create: raise ProviderError()
        return deepcopy(value)

    def find_creation(self, row):
        return next((deepcopy(v) for v in self.remote.values() if v['notes']['vectra_attempt']==str(row['id'])), None)

    def subscription(self, provider_id): return deepcopy(self.remote[provider_id])
    def invoices(self, provider_id): return deepcopy(self.invoice_rows[provider_id])
    def payment(self, provider_id): return deepcopy(self.payment_rows[provider_id])

    def cancel(self, provider_id, at_period_end=True):
        self.cancel_calls += 1
        if not at_period_end: self.remote[provider_id]['status']='cancelled'
        return self.subscription(provider_id)

    def charge(self, provider_id, start=None, authorization=False):
        start = start or datetime.now(UTC)-timedelta(minutes=1)
        invoice_id, payment_id = 'inv_'+uuid4().hex, 'pay_'+uuid4().hex
        invoice = dict(id=invoice_id, subscription_id=provider_id, payment_id=payment_id, status='paid', currency='INR',
                       amount=10000, amount_paid=10000, amount_due=0,
                       line_items=[{'type':'plan','quantity':1,'amount':10000}],
                       billing_start=None if authorization else int(start.timestamp()),
                       billing_end=None if authorization else int((start+timedelta(days=30)).timestamp()),
                       paid_at=int(datetime.now(UTC).timestamp()))
        self.invoice_rows[provider_id].append(invoice)
        self.payment_rows[payment_id]=dict(id=payment_id,invoice_id=invoice_id,amount=10000,amount_refunded=0,
                                         currency='INR', status='captured',captured=True)
        self.remote[provider_id]['status']='authenticated' if authorization else 'active'
        return invoice, self.payment_rows[payment_id]
