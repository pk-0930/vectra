"""Small bounded Razorpay REST adapter. No automatic retry of subscription creation."""
import hashlib
import hmac
import re
import requests


class ProviderError(Exception):
    def __init__(self, code='provider_unavailable', definitive=False):
        super().__init__(code)
        self.code = code
        self.definitive = definitive


def verify_signature(body, signature, secret):
    return bool(secret and isinstance(signature, str) and re.fullmatch('[0-9a-f]{64}', signature)
                and hmac.compare_digest(hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(), signature))


class RazorpayService:
    def __init__(self, config, session=None):
        self.config = config
        self.session = session or requests.Session()

    @staticmethod
    def provider_id(value, prefix):
        if not isinstance(value, str) or not re.fullmatch(prefix + r'_[A-Za-z0-9]{1,80}', value):
            raise ProviderError('invalid_provider_reference', True)
        return value

    def request(self, method, path, **kwargs):
        if not self.config.key_id or not self.config.key_secret:
            raise ProviderError('billing_not_configured', True)
        try:
            response = self.session.request(method, 'https://api.razorpay.com/v1/' + path,
                auth=(self.config.key_id, self.config.key_secret), timeout=(5, 20), **kwargs)
        except requests.RequestException:
            raise ProviderError() from None
        if response.status_code >= 400:
            raise ProviderError('provider_rejected' if 400 <= response.status_code < 500 else 'provider_unavailable',
                                400 <= response.status_code < 500 and response.status_code not in {408, 429})
        try:
            result = response.json()
            if not isinstance(result, dict): raise ValueError()
            return result
        except ValueError:
            raise ProviderError('provider_invalid_response') from None

    def plan(self, provider_id):
        return self.request('GET', 'plans/' + self.provider_id(provider_id, 'plan'))

    def subscription(self, provider_id):
        return self.request('GET', 'subscriptions/' + self.provider_id(provider_id, 'sub'))

    def payment(self, provider_id):
        return self.request('GET', 'payments/' + self.provider_id(provider_id, 'pay'))

    def pages(self, path, params):
        # Never silently accept a truncated invoice/discovery result.
        for offset in range(0, 10000, 100):
            result = self.request('GET', path, params={**params, 'count': 100, 'skip': offset})
            items = result.get('items')
            if not isinstance(items, list): raise ProviderError('provider_invalid_response')
            yield from items
            if len(items) < 100: return
        raise ProviderError('provider_pagination_limit')

    def invoices(self, provider_id):
        return list(self.pages('invoices', {'subscription_id': self.provider_id(provider_id, 'sub')}))

    def find_creation(self, subscription):
        matches = [item for item in self.pages('subscriptions', {'from': int(subscription['created_at'].timestamp()) - 60})
                   if isinstance(item.get('notes'), dict) and item['notes'].get('vectra_attempt') == str(subscription['id'])]
        if len(matches) > 1: raise ProviderError('multiple_provider_subscriptions')
        return matches[0] if matches else None

    def create(self, subscription):
        plan = subscription['plan_snapshot']
        payload = {'plan_id': plan['razorpay_plan_id'], 'quantity': 1,
                   'total_count': plan['total_count'], 'customer_notify': True,
                   'notes': {'vectra_attempt': str(subscription['id']),
                             'vectra_organization': str(subscription['organization_id'])}}
        if subscription['start_at']:
            payload['start_at'] = int(subscription['start_at'].timestamp())
        return self.request('POST', 'subscriptions', json=payload)

    def cancel(self, provider_id, at_period_end=True):
        return self.request('POST', 'subscriptions/' + self.provider_id(provider_id, 'sub') + '/cancel',
                            json={'cancel_at_cycle_end': 1 if at_period_end else 0})
