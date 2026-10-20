"""Exercise the ASGI routes without loading local settings or external services."""
import asyncio
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from services.auth_service import AuthService


class AuthRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with ExitStack() as stack:
            stack.enter_context(patch('config.local_settings_loader.load_local_settings'))
            services = {
                'auth_service': 'AuthService', 'client_service': 'ClientService',
                'job_service': 'JobService', 'job_runner': 'JobRunner',
                'blob_storage_service': 'BlobStorageService', 'queue_service': 'QueueService',
                'plan_service': 'PlanService', 'ai_plan_draft_service': 'AiPlanDraftService',
                'pdf_service': 'PdfService', 'storage_asset_service': 'StorageAssetService',
            }
            for module, name in services.items():
                stack.enter_context(patch(f'services.{module}.{name}'))
            spec = importlib.util.spec_from_file_location('auth_test_app', Path(__file__).resolve().parents[1] / 'app.py')
            cls.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.module)

    def setUp(self):
        self.repository = Mock()
        self.repository.fetch_user_by_id.return_value = {"id": 7, "email": "member@example.invalid", "password_hash": "private"}
        self.repository.fetch_coach_by_user_id.return_value = None
        self.repository.list_user_organizations.return_value = [{
            "organization_id": 2, "name": "Gym", "organization_type": "gym",
            "relationship_id": 5, "staff_roles": [], "client_id": 9,
        }]
        self.security = Mock()
        self.security.decode_access_token.side_effect = lambda token: {"sub": 7} if token == 'valid' else None
        self.module.auth_service = AuthService(self.repository, self.security)

    def request(self, path, header=None, query='', method='GET'):
        async def run():
            messages = []
            async def receive():
                return {"type": "http.request", "body": b'', "more_body": False}
            async def send(message):
                messages.append(message)
            scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"}, "http_version": "1.1",
                     "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
                     "query_string": query.encode(), "root_path": "",
                     "headers": [] if header is None else [(b'authorization', header.encode())],
                     "client": ('test', 1), "server": ('test', 80)}
            if path == "/clients":
                scope["headers"].append((b"x-organization-id", b"999"))
            await self.module.app(scope, receive, send)
            status = next(m['status'] for m in messages if m['type'] == 'http.response.start')
            body = b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body')
            return status, json.loads(body)
        return asyncio.run(run())

    def test_member_identity_route_succeeds_but_coaching_route_is_forbidden(self):
        status, body = self.request('/auth/me', 'Bearer valid')
        self.assertEqual(status, 200)
        self.assertIsNone(body['coach'])
        self.assertEqual(body['organizations'][0]['client_id'], 9)
        self.assertNotIn('password_hash', body['user'])
        self.assertEqual(self.request('/clients', 'Bearer valid')[0], 403)
        self.module.client_service.list_clients.assert_not_called()

    def test_identity_route_requires_header_and_bad_header_cannot_use_query_fallback(self):
        self.assertEqual(self.request('/auth/me', query='token=valid')[0], 401)
        self.assertEqual(self.request('/auth/me', 'Bearer wrong')[0], 401)
        self.assertEqual(self.request('/clients', 'Bearer wrong', 'token=valid')[0], 401)
        self.assertEqual(self.request('/auth/me', 'bearer valid')[0], 200)

    def test_query_tokens_no_longer_authenticate_coaching_routes(self):
        self.assertEqual(self.request('/clients', query='token=valid')[0], 401)

    def test_unverified_identity_can_restore_session_but_not_open_business(self):
        self.repository.fetch_user_by_id.return_value['verification_required'] = True
        self.assertEqual(self.request('/auth/me', 'Bearer valid')[0], 200)
        status, body = self.request('/clients', 'Bearer valid')
        self.assertEqual(status, 403)
        self.assertIn('Verify your email', body['detail'])

    def test_analysis_disabled_blocks_all_routes_before_auth_or_storage(self):
        routes = [('/form-analyses', 'GET'), ('/clients/1/form-analyses', 'GET'),
                  ('/clients/1/form-analyses', 'POST'), ('/form-analyses/example', 'GET'),
                  ('/form-analyses/example/feedback', 'PUT'), ('/form-analyses/example/pdf', 'GET'),
                  ('/jobs', 'GET'), ('/jobs/example', 'GET'), ('/jobs/squat', 'POST'),
                  ('/frames/example.jpg', 'GET')]
        with patch.dict('os.environ', {'FORM_ANALYSIS_ENABLED': 'false'}):
            self.assertEqual(self.request('/features'), (200, {'form_analysis': False}))
            for path, method in routes:
                with self.subTest(path=path, method=method):
                    self.assertEqual(self.request(path, method=method),
                                     (404, {'detail': 'Form analysis is disabled.'}))
        with patch.dict('os.environ', {'FORM_ANALYSIS_ENABLED': 'true'}):
            self.assertEqual(self.request('/features'), (200, {'form_analysis': True}))
            # Re-enabling never bypasses normal authentication.
            self.assertEqual(self.request('/form-analyses')[0], 401)
