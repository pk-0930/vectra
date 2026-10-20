"""Business software billing. Provider state is refreshed; browser callbacks never grant access."""
from datetime import UTC, datetime, timedelta
import hashlib
import json
from uuid import UUID

from config.billing_config import get_billing_config
from repositories.access_repository import AccessDenied
from services.razorpay_service import ProviderError, RazorpayService, verify_signature

TERMINAL = {'cancelled', 'completed', 'expired', 'creation_failed'}
REMOTE_STATES = {'created', 'authenticated', 'active', 'pending', 'halted', 'paused', 'cancelled', 'completed', 'expired'}


def access_state(organization, payments, now=None):
    now = now or datetime.now(UTC)
    valid = [p for p in payments if p['refunded_paise'] < p['amount_paise']]
    current = [p for p in valid if p['period_start'] <= now < p['period_end']]
    paid_through = max((p['period_end'] for p in valid), default=None)
    if current:
        state = 'active'
    elif not payments and not organization['billing_required'] and (not organization['billing_legacy_until'] or now < organization['billing_legacy_until']):
        state = 'legacy'
    else:
        expired = [p for p in valid if p['period_end'] <= now]
        latest = max(expired, key=lambda p: p['period_end'], default=None)
        grace_end = latest['period_end'] + timedelta(days=latest['plan_snapshot']['grace_days']) if latest else None
        state = 'grace' if grace_end and now < grace_end else 'read_only' if payments or not organization['billing_required'] else 'pending'
    expired = [p for p in valid if p['period_end'] <= now]
    latest = max(expired, key=lambda p: p['period_end'], default=None)
    return {'access': state, 'paid_through': paid_through,
            'grace_until': latest['period_end'] + timedelta(days=latest['plan_snapshot']['grace_days']) if latest else None,
            'legacy_until': organization['billing_legacy_until']}


class BillingService:
    def __init__(self, repository, config=None, provider=None):
        self.repository = repository
        self.config = config or get_billing_config()
        self.provider = provider or RazorpayService(self.config)

    def state(self, db, org):
        return access_state(self.repository.organization(db, org), self.repository.payments(db, org, self.config.mode))

    @staticmethod
    def require_verified(user):
        if user.get('verification_required'):
            raise AccessDenied('Verify your email before setting up billing.')

    def create_business(self, user, request_id, name, kind):
        self.require_verified(user)
        name = name.strip()
        if kind not in {'gym','coaching'} or not 1 <= len(name) <= 120:
            raise ValueError('Enter a business name and select gym or online coaching.')
        with self.repository.transaction() as db:
            org = self.repository.create_business(db, user['id'], request_id, name, kind)
        return {'organization_id': org}

    def summary(self, user, org):
        with self.repository.transaction() as db:
            access = self.repository.authorize(db, org, user['id'])
            organization = self.repository.organization(db, org)
            payments = self.repository.payments(db, org, self.config.mode)
            result = {**access_state(organization, payments), 'mode': self.config.mode,
                      'owner': 'owner' in access.roles, 'checkout_available': self.config.enabled,
                      'business_name': organization['name'], 'business_type': organization['organization_type']}
            if not result['owner']: return result
            subs = self.repository.subscriptions(db, org, self.config.mode)
            result.update({
                'plans': [{k: p[k] for k in ('code','name','business_type','amount_paise','period','interval','total_count')}
                          for p in self.config.plans if p['business_type'] == organization['organization_type']],
                'terms_version': self.config.terms_version,
                'terms': f'Recurring Vectra software subscription. Renewal grace: {self.config.grace_days} days. '
                         'After expiry, existing records remain readable; changes require renewal. '
                         'Cancellation stops future renewals at the end of the billing period. Refunds require support review; '
                         'full refunds remove the refunded period. A successful first payment ends legacy access.',
                'subscription': self.public_subscription(subs[0]) if subs else None,
                'payments': [{k: p[k] for k in ('payment_id','invoice_id','amount_paise','refunded_paise','currency','period_start','period_end','paid_at')} for p in payments],
            })
            return result

    def public_subscription(self, row):
        return {**{k: row[k] for k in ('id','provider_id','status','cancel_requested','cancel_confirmed','error_code','created_at')},
                'plan': row['plan_snapshot'], 'key_id': self.config.key_id if row['provider_id'] else None}

    def start_subscription(self, user, org, code, terms_version):
        self.require_verified(user)
        if not self.config.enabled: raise ValueError('Software checkout is not configured yet. Your onboarding is saved.')
        if terms_version != self.config.terms_version: raise ValueError('Review the current billing terms before continuing.')
        plan = next((p for p in self.config.plans if p['code'] == code), None)
        if not plan: raise ValueError('Plan is unavailable.')
        with self.repository.transaction() as db:
            organization = self.repository.organization(db, org, lock=True)
            self.repository.authorize(db, org, user['id'], owner=True)
            if plan['business_type'] != organization['organization_type']: raise ValueError('Plan does not match this business type.')
            subs = self.repository.subscriptions(db, org, self.config.mode)
            current = next((s for s in subs if s['closed_at'] is None), None)
            if current:
                if current['plan_snapshot']['code'] != code: raise ValueError('Finish or cancel the existing subscription before changing plans.')
                return self.public_subscription(current)
            payments = self.repository.payments(db, org, self.config.mode)
            state = access_state(organization, payments)
            start = state['paid_through'] if state['access'] == 'active' else None
            snapshot = {**plan, 'grace_days': self.config.grace_days, 'currency': 'INR'}
            row = self.repository.insert_subscription(db, org, user['id'], self.config, snapshot, start)
            return self.public_subscription(row)

    def cancel(self, user, org):
        self.require_verified(user)
        with self.repository.transaction() as db:
            self.repository.organization(db, org, lock=True)
            self.repository.authorize(db, org, user['id'], owner=True)
            row = next((s for s in self.repository.subscriptions(db, org, self.config.mode) if not s['closed_at']), None)
            if row: self.repository.request_cancel(db, row)
        return {'message': 'Cancellation requested. Paid coverage remains until its end date; provider confirmation is pending.'}

    def refresh(self, user, org, callback=None):
        with self.repository.transaction() as db:
            self.repository.authorize(db, org, user['id'], owner=True)
            subs = self.repository.subscriptions(db, org, self.config.mode)
            if not subs: raise ValueError('No subscription to refresh.')
            row = subs[0]
            if callback:
                if callback['razorpay_subscription_id'] != row['provider_id'] or not verify_signature(
                        f"{callback['razorpay_payment_id']}|{row['provider_id']}".encode(),
                        callback['razorpay_signature'], self.config.key_secret):
                    raise ValueError('Checkout verification failed.')
            if not row['provider_id'] and row['closed_at']:
                return {'message': 'This checkout is closed. Choose a plan to start a new checkout.'}
            self.repository.schedule_sync(db, row)
        return {'message': 'Payment verification queued. Authorization alone does not activate access.'}

    def webhook(self, raw, signature, event_id):
        if not verify_signature(raw, signature, self.config.webhook_secret):
            raise AccessDenied('Invalid webhook signature.')
        if not event_id or len(event_id) > 200: raise ValueError('A webhook event ID is required.')
        try:
            event = json.loads(raw)
            kind = event['event']
            if not isinstance(kind, str) or len(kind) > 100: raise ValueError()
            entity = event.get('payload', {}).get('subscription', {}).get('entity', {})
            provider_id = entity.get('id') if kind.startswith('subscription.') else None
            if provider_id: self.provider.provider_id(provider_id, 'sub')
        except (ValueError, KeyError, TypeError, AttributeError, ProviderError):
            raise ValueError('Invalid webhook event.') from None
        self.repository.record_webhook(self.config.mode, event_id, hashlib.sha256(raw).hexdigest(), kind, provider_id)
        return {'received': True}

    @staticmethod
    def validate_plan(plan, remote):
        if (remote.get('id') != plan['razorpay_plan_id'] or remote.get('period') != plan['period']
                or remote.get('interval') != plan['interval'] or remote.get('item', {}).get('amount') != plan['amount_paise']
                or remote.get('item', {}).get('currency') != 'INR'):
            raise ProviderError('provider_plan_mismatch', True)

    @staticmethod
    def validate_subscription(row, remote):
        if (remote.get('plan_id') != row['plan_snapshot']['razorpay_plan_id'] or remote.get('quantity') != 1
                or remote.get('total_count') != row['plan_snapshot']['total_count']
                or remote.get('status') not in REMOTE_STATES
                or remote.get('notes', {}).get('vectra_attempt') != str(row['id'])
                or remote.get('notes', {}).get('vectra_organization') != str(row['organization_id'])
                or (row['provider_id'] and remote.get('id') != row['provider_id'])):
            raise ProviderError('provider_subscription_mismatch')
        RazorpayService.provider_id(remote.get('id'), 'sub')

    @staticmethod
    def verified_payment(row, remote, invoice, payment):
        plan = row['plan_snapshot']
        lines = invoice.get('line_items', [])
        if (invoice.get('subscription_id') != remote['id'] or invoice.get('status') != 'paid'
                or invoice.get('payment_id') != payment.get('id') or payment.get('invoice_id') != invoice.get('id')
                or invoice.get('currency') != 'INR' or payment.get('currency') != 'INR'
                or invoice.get('amount') != plan['amount_paise'] or invoice.get('amount_paid') != plan['amount_paise']
                or invoice.get('amount_due') != 0 or payment.get('amount') != plan['amount_paise']
                or payment.get('status') not in {'captured','refunded'} or payment.get('captured') is not True
                or len(lines) != 1 or lines[0].get('type') != 'plan' or lines[0].get('quantity') != 1
                or lines[0].get('amount') != plan['amount_paise']
                or (invoice.get('order_id') and payment.get('order_id') != invoice['order_id'])):
            raise ProviderError('payment_verification_mismatch')
        try:
            values = [invoice[k] for k in ('billing_start','billing_end','paid_at')]
            if any(type(v) is not int or v <= 0 for v in values): raise ValueError()
            start, end, paid = [datetime.fromtimestamp(v, UTC) for v in values]
            days = (end-start).total_seconds()/86400
            low, high = (27,32) if plan['period'] == 'monthly' else (364,367)
            if not low*plan['interval'] <= days <= high*plan['interval']: raise ValueError()
            refund = payment.get('amount_refunded', 0)
            if type(refund) is not int or not 0 <= refund <= plan['amount_paise']: raise ValueError()
        except (ValueError, KeyError, TypeError, OverflowError, OSError):
            raise ProviderError('invalid_payment_period') from None
        return dict(payment_id=payment['id'], invoice_id=invoice['id'], amount_paise=plan['amount_paise'],
                    refunded_paise=refund, currency='INR', period_start=start, period_end=end, paid_at=paid)

    def process_one(self):
        row = self.repository.claim_work(self.config.mode)
        if not row: return False
        if row['status'] == 'queued' and row['cancel_requested']:
            self.repository.cancel_uncreated(row)
            return True
        try:
            plan = row['plan_snapshot']
            self.validate_plan(plan, self.provider.plan(plan['razorpay_plan_id']))
            if row['provider_id']:
                remote = self.provider.subscription(row['provider_id'])
            elif row['status'] == 'queued':
                remote = self.provider.create(row)
            else:
                # Unknown network outcome/crash: discover by the durable attempt ID, never blindly POST again.
                remote = self.provider.find_creation(row)
                if remote is None: raise ProviderError('creation_requires_reconciliation')
            self.validate_subscription(row, remote)
            payments = []
            for invoice in self.provider.invoices(remote['id']):
                if invoice.get('status') != 'paid': continue
                # Authorization-only invoices have no service period and confer no access.
                if invoice.get('billing_start') is None or invoice.get('billing_end') is None: continue
                payment = self.provider.payment(invoice.get('payment_id'))
                payments.append(self.verified_payment(row, remote, invoice, payment))
            cancel_confirmed = row['cancel_confirmed']
            if row['cancel_requested'] and not cancel_confirmed:
                if remote['status'] not in TERMINAL:
                    remote = self.provider.cancel(remote['id'], at_period_end=remote['status'] == 'active')
                    self.validate_subscription(row, remote)
                cancel_confirmed = True
            with self.repository.transaction() as db:
                organization = self.repository.organization(db, row['organization_id'], lock=True)
                current = self.repository.lock_claim(db, row)
                if not current: return True
                for payment in payments:
                    created = self.repository.upsert_payment(db, row, payment)
                    if created:
                        self.repository.notify_owners(db, row['organization_id'], f"{row['mode']}:paid:{payment['invoice_id']}",
                            'Vectra software payment confirmed', f"Payment of INR {payment['amount_paise']/100:.2f} for {organization['name']} "
                            f"is verified. Coverage: {payment['period_start'].isoformat()} to {payment['period_end'].isoformat()}.")
                    if payment['refunded_paise']:
                        self.repository.notify_owners(db, row['organization_id'],
                            f"{row['mode']}:refund:{payment['payment_id']}:{payment['refunded_paise']}",
                            'Vectra software refund update',
                            f"A refund of INR {payment['refunded_paise']/100:.2f} is recorded for {organization['name']}. "
                            'Full refunds remove coverage for that invoice. Partial refunds preserve its service dates.')
                if remote['status'] in {'pending','halted','paused','cancelled','completed','expired'} and remote['status'] != current['status']:
                    self.repository.notify_owners(db, row['organization_id'], f"{row['id']}:{remote['status']}:{remote.get('current_end')}",
                        'Vectra software billing update', f"The software subscription for {organization['name']} is {remote['status']}. "
                        'Existing paid coverage is preserved. Open Billing in Vectra to review your access and payment history.')
                if cancel_confirmed and not current['cancel_confirmed']:
                    self.repository.notify_owners(db, row['organization_id'], f"{row['id']}:cancellation_confirmed",
                        'Vectra software renewal cancellation confirmed',
                        f"Future renewals for {organization['name']} have been cancelled. Existing paid coverage remains until its end date.")
                self.repository.finish_sync(db, row, remote, cancel_confirmed)
        except ProviderError as exc:
            self.repository.fail_sync(row, exc.code, definitive=exc.definitive and row['status'] == 'queued')
        except Exception:
            self.repository.fail_sync(row, 'billing_processing_failed')
        return True
