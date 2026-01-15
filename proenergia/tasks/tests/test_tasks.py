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
        current_app.conf.task_store_eager_result = True

    def test_hello_world_task_success(self):
        """Test hello world task executes successfully."""
        result = celery_tasks.hello_world_task.apply(["Alice"])

        self.assertTrue(result.successful())
        self.assertIn("message", result.result)
        self.assertEqual(result.result["message"], "Hello, Alice!")
        self.assertEqual(result.result["status"], "success")
        self.assertIn("task_id", result.result)
        self.assertIn("timestamp", result.result)

    def test_hello_world_task_default_name(self):
        """Test hello world task with default name."""
        result = celery_tasks.hello_world_task.apply()

        self.assertTrue(result.successful())
        self.assertEqual(result.result["message"], "Hello, World!")

    @patch("time.sleep")
    def test_hello_world_task_with_mock_sleep(self, mock_sleep):
        """Test hello world task with mocked sleep to speed up test."""
        result = celery_tasks.hello_world_task.apply(["Bob"])

        mock_sleep.assert_called_once_with(2)
        self.assertTrue(result.successful())
        self.assertEqual(result.result["message"], "Hello, Bob!")

    def test_task_result_database_storage(self):
        """Test that essential task results are stored in TaskResult for Django Admin."""
        from django_celery_results.models import TaskResult
        import json

        # Clear any existing task results
        TaskResult.objects.all().delete()

        # Execute a task
        name = "Database Test"
        result = celery_tasks.hello_world_task.apply([name])
        task_id = result.id

        # Verify TaskResult was created in database
        task_result = TaskResult.objects.get(task_id=task_id)

        # Test essential fields that are always populated in eager mode
        self.assertEqual(task_result.task_id, task_id)
        self.assertEqual(task_result.status, "SUCCESS")

        # Test result data is properly stored as JSON
        stored_result = json.loads(task_result.result)
        self.assertEqual(stored_result["message"], f"Hello, {name}!")
        self.assertEqual(stored_result["status"], "success")
        self.assertIn("task_id", stored_result)
        self.assertIn("timestamp", stored_result)

        # Test timestamps are populated
        self.assertIsNotNone(task_result.date_created)
        self.assertIsNotNone(task_result.date_done)
        self.assertIsNone(task_result.traceback)  # No error occurred
