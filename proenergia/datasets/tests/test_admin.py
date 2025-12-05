from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from proenergia.datasets.models import VectorDataset


class VectorDatasetAdmin(TestCase):
    def setUp(self):
        self.client = Client()
        # Create superuser for admin access
        self.admin_user = get_user_model().objects.create_superuser(
            username="admin", email="admin@example.com", password="testpass123"
        )

        # Create regular user
        self.admin_user_2 = get_user_model().objects.create_superuser(
            username="admin_user_2",
            email="admin_user_2@example.com",
            password="testpass123",
        )

    def test_creation(self):
        self.client.login(username="admin", password="testpass123")
        url = reverse("admin:datasets_vectordataset_add")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = {
            "name": "Test Dataset",
            "description": "Test Description",
        }
        response = self.client.post(url, data)

        # Should redirect to changelist after successful creation
        self.assertEqual(response.status_code, 302)

        # Verify that it was created with the correct user
        dataset = VectorDataset.objects.get(name="Test Dataset")
        self.assertEqual(dataset.created_by, self.admin_user)
        self.assertEqual(dataset.last_updated_by, self.admin_user)

    def test_update(self):
        dataset = VectorDataset.objects.create(
            name="Test Dataset",
            description="Test Description",
            created_by=self.admin_user,
            last_updated_by=self.admin_user,
        )
        self.client.login(username="admin_user_2", password="testpass123")
        url = reverse("admin:datasets_vectordataset_change", args=[dataset.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = {
            "name": "Test Dataset",
            "description": "Updated Description",
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)

        dataset.refresh_from_db()
        self.assertEqual(dataset.name, "Test Dataset")
        self.assertEqual(dataset.description, "Updated Description")
        self.assertEqual(dataset.created_by, self.admin_user)
        self.assertEqual(dataset.last_updated_by, self.admin_user_2)
