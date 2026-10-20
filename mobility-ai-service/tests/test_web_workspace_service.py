import unittest
from datetime import date
from unittest.mock import Mock, patch
from repositories.access_repository import AccessDenied
from services.web_workspace_service import WebWorkspaceService
from scripts.web_release_check import configuration_checks


class WebWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.repo = Mock()
        self.service = WebWorkspaceService(self.repo)
        self.access = Mock(roles={'owner'})

    def test_invalid_announcements_do_not_write(self):
        for audience, subject, message in [('foreign', 'Hello', 'World'), ('all', ' ', 'World'), ('all', 'Hello', ' '), ('all', 'x'*161, 'World')]:
            with self.subTest(audience=audience, subject=subject), self.assertRaises(ValueError):
                self.service.announce(self.access, 'request', audience, subject, message)
        self.repo.announce.assert_not_called()

    def test_announcement_permission_is_checked_before_storage(self):
        self.access.require_admin.side_effect = AccessDenied('No')
        with self.assertRaises(AccessDenied):
            self.service.announce(self.access, 'request', 'all', 'Subject', 'Message')
        self.repo.announce.assert_not_called()

    def test_report_interval_and_india_default(self):
        with patch('services.web_workspace_service.today_india', return_value=date(2026, 10, 20)):
            self.service.reports(self.access)
        self.repo.reports.assert_called_once_with(self.access, date(2026, 10, 1), date(2026, 10, 20), date(2026, 10, 20))
        with self.assertRaises(ValueError): self.service.reports(self.access, date(2024, 1, 1), date(2026, 1, 1))

    def test_only_owner_can_pause_new_purchases(self):
        self.access.roles = {'admin'}
        with self.assertRaises(AccessDenied): self.service.set_rollout(self.access, False)
        self.repo.set_rollout.assert_not_called()

    def test_release_check_fails_closed_without_configuration(self):
        with patch.dict('os.environ', {}, clear=True):
            result = configuration_checks('production')
        self.assertFalse(result['authentication'])
        self.assertFalse(result['billing_enabled'])
        self.assertFalse(result['email_configured'])
        self.assertFalse(result['cloud_storage_configured'])

    def test_readiness_fails_without_exposing_database_error(self):
        self.repo.ready.side_effect = RuntimeError('sensitive connection details')
        self.assertFalse(self.service.ready(Mock()))

    def test_deployment_plan_covers_all_workers_and_rejects_mutable_tag(self):
        from argparse import Namespace
        from scripts.deploy_web_containers import release_commands
        args = Namespace(commit='a'*40, registry='fixture.azurecr.io', subscription='fixture-subscription',
                         resource_group='fixture', api='api', analysis_worker='analysis', email_worker='email',
                         billing_worker='billing', membership_job='membership')
        commands = release_commands(args)
        self.assertEqual(len(commands), 5)
        self.assertTrue(any('email_worker.py' in command for command in commands))
        self.assertTrue(any('billing_worker.py' in command for command in commands))
        self.assertTrue(any('membership_worker.py' in command for command in commands))
        args.commit = 'latest'
        with self.assertRaises(ValueError): release_commands(args)
