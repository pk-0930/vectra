import base64
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import os
import secrets
import unittest
from unittest.mock import Mock, patch

from config.auth_config import AuthConfig, get_auth_config
from services.auth_service import AuthService
from services.security_service import SecurityService


class IdentitySessionTests(unittest.TestCase):
    def setUp(self):
        self.security = SecurityService(AuthConfig(secrets.token_urlsafe(32), 24))
        self.repository = Mock()
        self.user = {"id": 7, "email": "person@example.invalid", "password_hash": "private"}
        self.repository.fetch_user_by_id.return_value = self.user
        self.repository.fetch_user_by_email.return_value = self.user
        self.repository.fetch_coach_by_user_id.return_value = None
        self.repository.list_user_organizations.return_value = []
        self.service = AuthService(self.repository, self.security)
        self.token = self.security.create_access_token(user_id=7, email=self.user["email"])

    def signed(self, payload):
        raw = json.dumps(payload).encode()
        signature = hmac.new(self.security.config.token_secret.encode(), raw, hashlib.sha256).digest()
        return '.'.join(base64.urlsafe_b64encode(part).rstrip(b'=').decode() for part in (raw, signature))

    def test_account_without_coach_can_sign_in_and_restore_session(self):
        with patch.object(self.security, 'verify_password', return_value=True):
            response = self.service.sign_in(email=" PERSON@example.invalid ", password="password")
        self.repository.fetch_user_by_email.assert_called_with("person@example.invalid")
        self.assertIsNone(response["coach"])
        self.assertEqual(response["organizations"], [])
        context = self.service.get_authenticated_user(response["access_token"])
        restored = self.service.session_response(context)
        self.assertEqual(restored["user"], {"id": 7, "email": self.user["email"], "email_verified": False, "verification_required": False})
        self.assertNotIn("password_hash", restored["user"])
        self.assertIsNone(restored["coach"])
        self.repository.create_coach.assert_not_called()

    def test_same_token_refreshes_relationships_and_does_not_grant_roles(self):
        self.repository.list_user_organizations.side_effect = [
            [{"organization_id": 1, "staff_roles": ["trainer"], "client_id": 10}],
            [{"organization_id": 1, "staff_roles": [], "client_id": 10}], [],
        ]
        self.assertEqual(self.service.get_authenticated_user(self.token)["organizations"][0]["staff_roles"], ["trainer"])
        self.assertEqual(self.service.get_authenticated_user(self.token)["organizations"][0]["client_id"], 10)
        self.assertEqual(self.service.get_authenticated_user(self.token)["organizations"], [])
        self.assertNotIn("organizations", self.security.decode_access_token(self.token))

    def test_deleted_identity_and_bad_credentials_are_rejected(self):
        self.repository.fetch_user_by_id.return_value = None
        self.assertIsNone(self.service.get_authenticated_user(self.token))
        with patch.object(self.security, 'verify_password', return_value=False):
            with self.assertRaisesRegex(ValueError, "Invalid email or password"):
                self.service.sign_in(email=self.user["email"], password="wrong")

    def test_malformed_signed_subjects_never_reach_repository(self):
        for subject in (None, True, False, 0, -1, "7", "oops", [], {}, 2**63):
            with self.subTest(subject=subject):
                token = self.signed({"sub": subject, "exp": (datetime.now(UTC) + timedelta(hours=1)).isoformat()})
                self.assertIsNone(self.service.get_authenticated_user(token))
        self.repository.fetch_user_by_id.assert_not_called()

    def test_expired_tampered_and_malformed_tokens_are_rejected(self):
        for token in ("", "garbage", "a.b.c", "x" * 8193, self.token + "x",
                      self.signed([]), self.signed({"sub": 7}),
                      self.signed({"sub": 7, "exp": "bad"}),
                      self.signed({"sub": 7, "exp": "2999-01-01T00:00:00"}),
                      self.signed({"sub": 7, "exp": "2000-01-01T00:00:00+00:00"})):
            with self.subTest(token=token[:20]):
                self.assertIsNone(self.security.decode_access_token(token))

    def test_legacy_coach_response_keeps_profile_shape(self):
        coach = dict(id=2, user_id=7, first_name="Test", last_name="Coach", dob=None,
                     gender=None, mobile=None, years_of_experience=0, associated_gym=None, clients_trained=0)
        self.repository.fetch_coach_by_user_id.return_value = coach
        self.assertEqual(self.service.session_response(self.service.get_authenticated_user(self.token))["coach"], coach)

    def test_password_hash_round_trip(self):
        hashed = self.security.hash_password("a-test-password")
        self.assertTrue(self.security.verify_password("a-test-password", hashed))
        self.assertFalse(self.security.verify_password("wrong", hashed))


class AuthConfigTests(unittest.TestCase):
    def test_missing_or_weak_secret_fails_closed(self):
        for secret in ("", "vectra-dev-secret", "short", " " * 40):
            with self.subTest(secret=secret), patch.dict(os.environ, {"AUTH_TOKEN_SECRET": secret}, clear=True):
                with self.assertRaisesRegex(ValueError, "AUTH_TOKEN_SECRET"):
                    get_auth_config()

    def test_valid_configuration_and_invalid_lifetimes(self):
        with patch.dict(os.environ, {"AUTH_TOKEN_SECRET": secrets.token_urlsafe(32)}, clear=True):
            self.assertEqual(get_auth_config().token_expiration_hours, 24)
            for expiration in ("0", "-1", "x"):
                with patch.dict(os.environ, {"AUTH_TOKEN_EXPIRATION_HOURS": expiration}):
                    with self.assertRaisesRegex(ValueError, "positive integer"):
                        get_auth_config()
