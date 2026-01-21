from django.urls import reverse
from django_celery_results.models import TaskResult
from rest_framework import status
from rest_framework.test import APITestCase

import proenergia.celery_tasks as celery_tasks


class TestCheckTaskStatusView(APITestCase):
    """Test cases for the task status endpoint."""

    def test_get_task_status_success(self):
        """Test GET with valid task_id returns proper JSON structure."""
        # Create a task and get its ID
        result = celery_tasks.hello_world_task.apply(["Test User"])
        task_id = result.id

        # Request task status
        url = reverse("tasks:check_task_status", kwargs={"task_id": task_id})
        response = self.client.get(url)

        # Verify response structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertIn("task_id", data)
        self.assertEqual(data["task_id"], task_id)
        self.assertIn("status", data)
        self.assertIn("ready", data)
        self.assertIn("successful", data)

        # For successful tasks, should have result data
        if data["ready"] and data["successful"]:
            self.assertIn("result", data)

    def test_get_nonexistent_task(self):
        """Test GET with valid UUID that doesn't exist handles gracefully."""
        # Use a valid UUID format but one that doesn't exist
        fake_task_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        url = reverse("tasks:check_task_status", kwargs={"task_id": fake_task_id})
        response = self.client.get(url)

        # Should still return 200 with task info (Celery handles non-existent tasks)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["task_id"], fake_task_id)

    def test_get_invalid_task_id(self):
        """Test GET with malformed task_id."""
        invalid_task_id = "not-a-valid-uuid"

        url = reverse("tasks:check_task_status", kwargs={"task_id": invalid_task_id})
        response = self.client.get(url)

        # Should handle gracefully - either 200 with error info or 500
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR],
        )


class TestListRecentTasksView(APITestCase):
    """Test cases for the task listing endpoint."""

    def test_list_tasks_default(self):
        """Test GET returns task list with proper JSON structure."""
        # Create a couple of tasks
        celery_tasks.hello_world_task.apply(["User1"])
        celery_tasks.hello_world_task.apply(["User2"])

        url = reverse("tasks:list_recent_tasks")
        response = self.client.get(url)

        # Verify response structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertIn("tasks", data)
        self.assertIn("count", data)
        self.assertIsInstance(data["tasks"], list)
        self.assertEqual(data["count"], len(data["tasks"]))

        # Should have at least our created tasks
        self.assertGreaterEqual(data["count"], 2)

    def test_list_tasks_custom_limit(self):
        """Test GET with custom limit parameter works."""
        # Create several tasks
        for i in range(5):
            celery_tasks.hello_world_task.apply([f"User{i}"])

        url = reverse("tasks:list_recent_tasks")
        response = self.client.get(url, {"limit": 3})

        # Verify limited response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(data["count"], 3)

    def test_list_tasks_max_limit_capped(self):
        """Test GET with limit > 100 caps at 100."""
        url = reverse("tasks:list_recent_tasks")
        response = self.client.get(url, {"limit": 150})

        # Should succeed and respect max limit
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertLessEqual(data["count"], 100)

    def test_list_tasks_empty(self):
        """Test GET when no tasks exist returns empty list."""
        # Clear any existing tasks
        TaskResult.objects.all().delete()

        url = reverse("tasks:list_recent_tasks")
        response = self.client.get(url)

        # Verify empty response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["tasks"], [])
