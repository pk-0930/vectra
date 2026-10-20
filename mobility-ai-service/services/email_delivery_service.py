"""Durable email delivery. Database locks exclude duplicate concurrent work.

ACS operation IDs stay stable across retries, including a crash after submission.
Transport delivery is at-least-once; identity actions remain strictly single-use.
"""
import os
from datetime import UTC, datetime
from urllib.parse import urlencode, urlsplit


class AcsEmailAdapter:
    def __init__(self, client=None, sender=None):
        self.sender = sender or os.environ.get('AZURE_COMMUNICATION_SERVICES_SENDER_ADDRESS', '')
        if client is None:
            from azure.communication.email import EmailClient
            connection = os.environ.get('AZURE_COMMUNICATION_SERVICES_CONNECTION_STRING', '')
            if not connection or not self.sender:
                raise ValueError('Configure ACS connection and sender before starting the email worker.')
            client = EmailClient.from_connection_string(connection, logging_enable=False,
                                                        connection_timeout=10, read_timeout=30)
        self.client = client

    def send(self, *, operation_id, recipient, subject, text):
        result = self.client.begin_send({
            'senderAddress': self.sender,
            'recipients': {'to': [{'address': recipient}]},
            'content': {'subject': subject, 'plainText': text},
        }, operation_id=str(operation_id), logging_enable=False).result(timeout=60)
        if not result or result.get('status') != 'Succeeded':
            raise RuntimeError('Provider did not confirm submission.')


def public_web_url():
    value = os.environ.get('PUBLIC_WEB_BASE_URL', '').rstrip('/')
    parsed = urlsplit(value)
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not (parsed.scheme == 'https' or (parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1'}))):
        raise ValueError('PUBLIC_WEB_BASE_URL must be HTTPS (HTTP is allowed for local development).')
    return value


class EmailDeliveryService:
    def __init__(self, repository, identity, adapter, base_url):
        self.repository = repository
        self.identity = identity
        self.adapter = adapter
        self.base_url = base_url

    def process_one(self):
        with self.repository.transaction() as db:
            row = self.repository.claim_delivery(db)
            if not row:
                return False
            if row.get('billing_notification_id'):
                subject, text = row['subject'], row['message'] + f"\n\nOpen Vectra: {self.base_url}"
                recipient = row['recipient']
            else:
                if row['revoked_at'] or row['consumed_at'] or row['expires_at'] <= datetime.now(UTC):
                    self.repository.cancel_delivery(db, (row['id'],))
                    return True
                token = self.identity.token(row['action_id'])
                if self.identity.digest(token) != row['token_hash']:
                    self.repository.fail_rotated_key_delivery(db, (row['id'],))
                    return True
                # Fragments never reach HTTP/access logs or Referer headers.
                path = f"/join/{row['return_gym_public_id']}" if row.get('return_gym_public_id') and row['kind'] == 'verify' else '/'
                link = f"{self.base_url}{path}#" + urlencode({'action': row['kind'], 'token': token})
                subject, intro = {
                    'verify': ('Verify your Vectra email', 'Confirm your email to open your workspace.'),
                    'recover': ('Reset your Vectra password', 'Reset your password. This signs out all existing sessions.'),
                    'invite': ('Your Vectra staff invitation', f"Join {row['business_name']} as {row['role']}."),
                }[row['kind']]
                text = f"{intro}\n\n{link}\n\nExpires: {row['expires_at'].isoformat()}\nIf you did not expect this email, ignore it."
                recipient = row['email']
            try:
                self.adapter.send(operation_id=row['id'], recipient=recipient, subject=subject, text=text)
            except Exception:
                # Never persist/log exception strings: provider errors may contain message/credential material.
                attempts = row['attempts'] + 1
                self.repository.retry_delivery(db, (attempts, 'failed' if attempts >= 5 else 'pending', min(3600, 30 * 2 ** attempts), row['id']))
            else:
                self.repository.complete_delivery(db, (row['id'],))
            return True
