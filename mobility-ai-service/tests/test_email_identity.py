from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import secrets
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from config.auth_config import AuthConfig
from repositories.identity_repository import IdentityRepository
from services.auth_service import AuthService
from services.email_delivery_service import AcsEmailAdapter, EmailDeliveryService, public_web_url
from services.identity_service import IdentityService, INVALID_LINK
from services.security_service import SecurityService


class FakeOutbox(IdentityRepository):
    def __init__(self, row):
        self.row = row
        self.db = Mock()
        self.db.execute.side_effect = self.execute

    @contextmanager
    def transaction(self):
        yield self.db

    def claim_delivery(self, db):
        return self.row if self.row['status'] == 'pending' else None

    def execute(self, sql, params):
        if "error_code='provider_send_failed'" in sql:
            self.row.update(attempts=params[0], status=params[1], error_code='provider_send_failed')
        elif "status='sent'" in sql:
            self.row['status'] = 'sent'
        elif "status='cancelled'" in sql:
            self.row['status'] = 'cancelled'
        elif "status='failed'" in sql:
            self.row['status'] = 'failed'


class EmailIdentityTests(unittest.TestCase):
    def setUp(self):
        self.security = SecurityService(AuthConfig(secrets.token_urlsafe(32), 24))
        self.identity = IdentityService(Mock(), self.security)
        action_id = uuid4()
        self.row = dict(id=uuid4(), action_id=action_id, kind='invite', email='person@example.invalid',
                        role='trainer', business_name='Gym', consumed_at=None, revoked_at=None,
                        expires_at=datetime.now(UTC)+timedelta(days=1), status='pending', attempts=0,
                        token_hash=self.identity.digest(self.identity.token(action_id)))
        self.repository = FakeOutbox(self.row)
        self.adapter = Mock()
        self.worker = EmailDeliveryService(self.repository, self.identity, self.adapter, 'https://example.invalid')

    def test_retry_keeps_operation_id_and_duplicate_work_does_not_resend(self):
        self.adapter.send.side_effect = [RuntimeError('secret token in provider error'), None]
        self.assertTrue(self.worker.process_one())
        self.assertEqual(self.row['status'], 'pending')
        self.assertEqual(self.row['error_code'], 'provider_send_failed')
        self.assertNotIn('secret token', str(self.repository.db.execute.call_args_list))
        self.assertTrue(self.worker.process_one())
        self.assertFalse(self.worker.process_one())
        self.assertEqual(self.adapter.send.call_count, 2)
        calls = self.adapter.send.call_args_list
        self.assertEqual(calls[0].kwargs['operation_id'], calls[1].kwargs['operation_id'])
        self.assertIn('/#action=invite&token=', calls[1].kwargs['text'])

    def test_billing_notice_uses_durable_delivery_without_identity_token(self):
        self.row.update(billing_notification_id=uuid4(), recipient='owner@example.invalid',
                        subject='Payment verified', message='Coverage renewed.', action_id=None)
        self.worker.identity = Mock()
        self.assertTrue(self.worker.process_one())
        self.assertEqual(self.row['status'], 'sent')
        sent = self.adapter.send.call_args.kwargs
        self.assertEqual(sent['recipient'], 'owner@example.invalid')
        self.assertEqual(sent['subject'], 'Payment verified')
        self.assertNotIn('token=', sent['text'])
        self.worker.identity.token.assert_not_called()
        self.assertFalse(self.worker.process_one())

    def test_gym_verification_returns_to_stable_join_path(self):
        public_id = uuid4()
        self.row.update(kind='verify', return_gym_public_id=public_id)
        self.worker.process_one()
        self.assertIn(f'/join/{public_id}#action=verify&token=', self.adapter.send.call_args.kwargs['text'])

    def test_terminal_failure_after_five_attempts(self):
        self.adapter.send.side_effect = RuntimeError('private contents')
        for _ in range(5): self.worker.process_one()
        self.assertEqual(self.row['status'], 'failed')
        self.assertFalse(self.worker.process_one())

    def test_stale_actions_are_not_sent(self):
        for field in ('revoked_at', 'consumed_at', 'expires_at'):
            self.row.update(status='pending', revoked_at=None, consumed_at=None,
                            expires_at=datetime.now(UTC)+timedelta(days=1))
            self.row[field] = datetime.now(UTC)-timedelta(seconds=1)
            self.worker.process_one()
            self.assertEqual(self.row['status'], 'cancelled')
        self.adapter.send.assert_not_called()

    def test_key_rotation_fails_closed(self):
        self.identity.security = SecurityService(AuthConfig(secrets.token_urlsafe(32), 24))
        self.worker.process_one()
        self.assertEqual(self.row['status'], 'failed')
        self.adapter.send.assert_not_called()

    def test_invalid_tokens_do_not_reach_database(self):
        for token in ('bad', 'é'*101, str(uuid4()), self.identity.token(uuid4())+'x'):
            with self.assertRaisesRegex(ValueError, INVALID_LINK):
                self.identity.consume(token, 'recover', password='long-enough-password')
        self.identity.repository.transaction.assert_not_called()

    def test_reset_session_version_invalidates_old_tokens(self):
        user = dict(id=7, email='person@example.invalid', session_version=1)
        repository = Mock()
        repository.fetch_user_by_id.return_value = user
        repository.list_user_organizations.return_value = []
        service = AuthService(repository, self.security)
        token = self.security.create_access_token(user_id=7, email=user['email'])
        self.assertIsNone(service.get_authenticated_user(token))
        fresh = self.security.create_access_token(user_id=7, email=user['email'], session_version=1)
        self.assertIsNotNone(service.get_authenticated_user(fresh))

    def test_acs_adapter_checks_provider_result(self):
        client = Mock()
        client.begin_send.return_value.result.return_value = {'status': 'Succeeded'}
        adapter = AcsEmailAdapter(client, 'sender@example.invalid')
        adapter.send(operation_id=self.row['id'], recipient=self.row['email'], subject='Test', text='Private')
        self.assertEqual(client.begin_send.call_args.kwargs['operation_id'], str(self.row['id']))
        client.begin_send.return_value.result.return_value = {'status': 'Failed'}
        with self.assertRaises(RuntimeError):
            adapter.send(operation_id=self.row['id'], recipient=self.row['email'], subject='Test', text='Private')

    def test_public_url_validation(self):
        for url in ('', 'http://example.com', 'https://u:p@example.com', 'https://example.com/#token'):
            with patch.dict('os.environ', {'PUBLIC_WEB_BASE_URL': url}):
                with self.assertRaises(ValueError): public_web_url()
        with patch.dict('os.environ', {'PUBLIC_WEB_BASE_URL': 'http://localhost:5173/'}):
            self.assertEqual(public_web_url(), 'http://localhost:5173')
