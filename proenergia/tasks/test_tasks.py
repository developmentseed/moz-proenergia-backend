import pytest
import time
from unittest.mock import patch
from django.test import TestCase
from celery import current_app
from celery.result import AsyncResult

import proenergia.tasks as celery_tasks


class TestHelloWorldTask(TestCase):
    """Test cases for the hello world task."""

    def setUp(self):
        """Set up test data."""
        # Configure Celery to execute tasks synchronously for testing
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
        
        # Verify sleep was called
        mock_sleep.assert_called_once_with(2)
        
        self.assertTrue(result.successful())
        self.assertEqual(result.result['message'], 'Hello, Bob!')

    def test_task_error_handling(self):
        """Test task error handling."""
        # This test demonstrates how to test error scenarios
        with patch('proenergia.tasks.time.sleep', side_effect=Exception('Test error')):
            result = celery_tasks.hello_world_task.apply(['Error Test'])
            
            self.assertFalse(result.successful())
            self.assertIsInstance(result.result, Exception)

    @patch('proenergia.tasks.logger')
    def test_task_logging(self, mock_logger):
        """Test that tasks log appropriately."""
        celery_tasks.hello_world_task.apply(['Logging Test'])
        
        # Verify logging was called
        mock_logger.info.assert_called()
        
        # Check that the log message contains expected content
        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        self.assertTrue(any('Starting hello_world_task' in msg for msg in log_calls))
        self.assertTrue(any('Completed hello_world_task' in msg for msg in log_calls))


class TestTaskIntegration(TestCase):
    """Integration tests for task functionality."""

    def setUp(self):
        """Set up test data."""
        # Configure Celery for synchronous execution
        current_app.conf.task_always_eager = True
        current_app.conf.task_eager_propagates = True

    def test_task_result_retrieval(self):
        """Test retrieving task results."""
        # Execute a task
        result = celery_tasks.hello_world_task.apply(['Integration Test'])
        task_id = result.id
        
        # Create an AsyncResult to test result retrieval
        async_result = AsyncResult(task_id)
        
        self.assertTrue(async_result.ready())
        self.assertTrue(async_result.successful())
        self.assertEqual(async_result.result['message'], 'Hello, Integration Test!')

    def test_multiple_tasks_execution(self):
        """Test executing multiple tasks."""
        tasks = []
        
        # Execute multiple tasks
        for i in range(5):
            task_result = celery_tasks.hello_world_task.apply([f'User{i}'])
            tasks.append(task_result)
        
        # Verify all tasks completed successfully
        for i, task in enumerate(tasks):
            self.assertTrue(task.successful())
            expected_message = f'Hello, User{i}!'
            self.assertEqual(task.result['message'], expected_message)


class TestTaskAsync(TestCase):
    """Test cases for async task execution."""

    def setUp(self):
        """Set up test data with async execution."""
        # Configure Celery to execute tasks asynchronously for testing
        current_app.conf.task_always_eager = False
        current_app.conf.task_eager_propagates = False

    def tearDown(self):
        """Clean up after async tests."""
        # Reset to synchronous mode
        current_app.conf.task_always_eager = True
        current_app.conf.task_eager_propagates = True

    @pytest.mark.skipif(
        not hasattr(current_app, 'control'),
        reason="Celery worker not available for async testing"
    )
    def test_async_task_execution(self):
        """Test task execution in async mode (requires running worker)."""
        # This test would require a running Celery worker
        # It's marked to skip if no worker is available
        
        task = celery_tasks.hello_world_task.delay('Async Test')
        
        # Wait for task completion (with timeout)
        timeout = 10
        start_time = time.time()
        
        while not task.ready() and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        if task.ready():
            self.assertTrue(task.successful())
            result = task.result
            self.assertEqual(result['message'], 'Hello, Async Test!')
        else:
            self.skip("Task did not complete within timeout - worker may not be running")


# Pytest-style tests for additional coverage
@pytest.mark.django_db
class TestHelloWorldTaskPytest:
    """Pytest-style tests for the hello world task."""

    def setup_method(self):
        """Set up for each test method."""
        current_app.conf.task_always_eager = True
        current_app.conf.task_eager_propagates = True

    def test_hello_world_task_with_special_characters(self):
        """Test hello world task with special characters in name."""
        special_names = ['José', 'Müller', '张三', '🚀 Rocket']
        
        for name in special_names:
            result = celery_tasks.hello_world_task.apply([name])
            assert result.successful()
            assert result.result['message'] == f'Hello, {name}!'

    @pytest.mark.parametrize("name,expected", [
        ('Alice', 'Hello, Alice!'),
        ('Bob', 'Hello, Bob!'),
        ('World', 'Hello, World!'),
        ('', 'Hello, !'),
        ('Test User', 'Hello, Test User!'),
    ])
    def test_hello_world_task_parametrized(self, name, expected):
        """Parametrized test for hello world task."""
        result = celery_tasks.hello_world_task.apply([name])
        assert result.successful()
        assert result.result['message'] == expected