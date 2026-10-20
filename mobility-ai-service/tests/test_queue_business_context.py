import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from services.queue_job_processor import NonRetryableQueueMessageError, RetryableQueueProcessingError, process_queue_message


class QueueBusinessContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch('config.local_settings_loader.load_local_settings'):
            spec = importlib.util.spec_from_file_location('isolated_queue_worker', Path(__file__).resolve().parents[1] / 'queue_worker.py')
            cls.worker = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.worker)

    def test_missing_invalid_or_cross_scope_messages_never_use_global_job_operations(self):
        for message in ([], {}, {'organization_id': True}, {'organization_id': '1'}, {'organization_id': 0}):
            root = Mock()
            with self.assertRaises(NonRetryableQueueMessageError):
                process_queue_message(root, Mock(), message)
            root.mark_job_running.assert_not_called()
            root.for_organization.assert_not_called()
        root = Mock()
        scoped = root.for_organization.return_value
        scoped.mark_job_running.return_value = None
        scoped.get_job.return_value = None
        with self.assertRaises(NonRetryableQueueMessageError):
            process_queue_message(root, Mock(), {'organization_id': 2, 'job_id': 'other-business', 'analysis_type': 'squat'})
        root.for_organization.assert_called_once_with(2)
        root.mark_job_running.assert_not_called()

    def run_worker(self, payload, error, count=1):
        queue, root, runner = Mock(), Mock(), Mock()
        queue.receive_analysis_job.return_value = Mock(id='message', content=json.dumps(payload), dequeue_count=count)
        config = Mock(visibility_timeout_seconds=1800, max_dequeue_count=3)
        with patch.object(self.worker, 'analysis_enabled', return_value=True), patch.object(self.worker, 'get_runtime_dependencies', return_value=(queue, root, runner)), patch.object(self.worker, 'get_queue_storage_config', return_value=config), patch.object(self.worker, 'process_queue_message', side_effect=error):
            self.assertEqual(self.worker.main(), 1)
        return queue, root

    def test_nonretryable_poison_does_not_mutate_a_job_named_by_untrusted_payload(self):
        queue, root = self.run_worker({'organization_id': 8, 'job_id': 'other'}, NonRetryableQueueMessageError('bad message'))
        queue.enqueue_poison_job.assert_called_once()
        root.for_organization.assert_not_called()
        root.mark_job_failed.assert_not_called()

    def test_retry_and_terminal_failure_use_business_scope(self):
        payload = {'organization_id': 8, 'job_id': 'analysis', 'analysis_type': 'squat'}
        queue, root = self.run_worker(payload, RetryableQueueProcessingError('temporary'))
        root.for_organization.assert_called_with(8)
        root.for_organization.return_value.requeue_job_for_retry.assert_called_once_with('analysis', 'temporary')
        queue.delete_analysis_job.assert_not_called()
        queue, root = self.run_worker(payload, RetryableQueueProcessingError('terminal'), count=3)
        root.for_organization.return_value.requeue_job_for_retry.assert_not_called()
        root.for_organization.return_value.mark_job_failed.assert_called_once_with('analysis', 'terminal')
        poison = queue.enqueue_poison_job.call_args.args[0]
        self.assertEqual(poison['payload']['organization_id'], 8)

    def test_unexpected_failure_cannot_requeue_an_unclaimed_job(self):
        _, root = self.run_worker({'organization_id': 8, 'job_id': 'target'}, RuntimeError('unexpected'))
        root.for_organization.assert_not_called()

    def test_disabled_worker_leaves_queue_and_storage_untouched(self):
        with patch.object(self.worker, 'analysis_enabled', return_value=False), patch.object(self.worker, 'get_runtime_dependencies') as dependencies:
            self.assertEqual(self.worker.main(), 0)
            dependencies.assert_not_called()
