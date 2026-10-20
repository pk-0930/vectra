"""Commercial values are deployment configuration, never invented production prices."""
from dataclasses import dataclass
import json
import os
import re


@dataclass(frozen=True)
class BillingConfig:
    mode: str = 'test'
    key_id: str = ''
    key_secret: str = ''
    webhook_secret: str = ''
    plans: tuple = ()
    grace_days: int = 7
    terms_version: str = 'software-v1'

    @property
    def enabled(self):
        return bool(self.key_id and self.key_secret and self.webhook_secret and self.plans)


def get_billing_config():
    mode = os.environ.get('RAZORPAY_MODE', 'test')
    key = os.environ.get('RAZORPAY_KEY_ID', '')
    grace = int(os.environ.get('SOFTWARE_BILLING_GRACE_DAYS', '7'))
    if mode not in {'test', 'live'} or not 0 <= grace <= 30:
        raise ValueError('Invalid billing mode or grace period.')
    if key and not key.startswith(f'rzp_{mode}_'):
        raise ValueError('Razorpay key must match the configured billing mode.')
    plans = json.loads(os.environ.get('SOFTWARE_PLANS_JSON', '[]'))
    seen = set()
    for plan in plans:
        if (not isinstance(plan, dict) or not re.fullmatch(r'[a-z0-9_-]{1,80}', plan.get('code', ''))
                or plan['code'] in seen or plan.get('business_type') not in {'gym', 'coaching'}
                or not isinstance(plan.get('name'), str) or not 1 <= len(plan['name']) <= 100
                or type(plan.get('amount_paise')) is not int or not 0 < plan['amount_paise'] <= 100000000
                or plan.get('period') not in {'monthly', 'yearly'}
                or type(plan.get('interval')) is not int or not 1 <= plan['interval'] <= 12
                or type(plan.get('total_count')) is not int or not 1 <= plan['total_count'] <= 120
                or not re.fullmatch(r'plan_[A-Za-z0-9]+', plan.get('razorpay_plan_id', ''))):
            raise ValueError('Invalid software plan configuration.')
        seen.add(plan['code'])
    return BillingConfig(mode, key, os.environ.get('RAZORPAY_KEY_SECRET', ''),
                         os.environ.get('RAZORPAY_WEBHOOK_SECRET', ''), tuple(plans), grace,
                         os.environ.get('SOFTWARE_TERMS_VERSION', 'software-v1'))
