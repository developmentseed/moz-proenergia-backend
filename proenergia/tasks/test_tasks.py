from unittest.mock import patch
from django.test import TestCase
from celery import current_app

import proenergia.celery_tasks as celery_tasks


class TestHelloWorldTask(TestCase):
    """Test cases for the hello world task."""

    def setUp(self):
        """Configure Celery to execute tasks synchronously for testing."""
        current_app.conf.task_always_eager = True
        current_app.conf.task_eager_propagates = True

    def test_hello_world_task_success(self):
        """Test hello world task executes successfully."""
        result = celery_tasks.hello_world_task.apply(['Alice'])

        self.assertTrue(result.successful())
        self.assertIn('message', result.result)
        self.assertEqual(result.result['message'], 'Hello, Alice!')
        self.assertEqual(result.result['status'], 'success')
        self.assertIn('task_id', result.result)
        self.assertIn('timestamp', result.result)

    def test_hello_world_task_default_name(self):
        """Test hello world task with default name."""
        result = celery_tasks.hello_world_task.apply()

        self.assertTrue(result.successful())
        self.assertEqual(result.result['message'], 'Hello, World!')

    @patch('time.sleep')
    def test_hello_world_task_with_mock_sleep(self, mock_sleep):
        """Test hello world task with mocked sleep to speed up test."""
        result = celery_tasks.hello_world_task.apply(['Bob'])

        mock_sleep.assert_called_once_with(2)
        self.assertTrue(result.successful())
        self.assertEqual(result.result['message'], 'Hello, Bob!')

    @patch('proenergia.celery_tasks.logger')
    def test_task_logging(self, mock_logger):
        """Test that tasks log appropriately."""
        celery_tasks.hello_world_task.apply(['Logging Test'])

        mock_logger.info.assert_called()
        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        self.assertTrue(any('Starting hello_world_task' in msg for msg in log_calls))
        self.assertTrue(any('Completed hello_world_task' in msg for msg in log_calls))
