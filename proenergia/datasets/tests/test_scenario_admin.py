import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from proenergia.datasets.models import Scenario, VectorDataset


class TestScenarioAdmin(TestCase):
    def setUp(self):
        self.superadmin_user = get_user_model().objects.create_superuser(
            username="superadmin",
            email="superadmin@example.com",
            password="testpass123",
        )
        self.dataset_1 = VectorDataset.objects.create(
            name="Boundaries",
            description="Administratives Boundaries",
            source="OSM",
            is_public=True,
            is_approved=True,
            created_by=self.superadmin_user,
            last_updated_by=self.superadmin_user,
        )
        self.url = reverse("admin:datasets_scenario_add")

    def test_validation(self):
        self.client.login(username="superadmin", password="testpass123")
        data = {
            "name": "Least Cost Eletrification",
            "vector_dataset": str(self.dataset_1.id),
            "filter_fields": json.dumps(
                [
                    {
                        "label": "Population",
                        "description": "Population in 2025",
                        "column": "Pop",
                    }
                ]
            ),
            "popup_fields": json.dumps(
                [
                    {
                        "label": "Population",
                        "description": "Population in 2025",
                        "column": "Pop",
                    }
                ]
            ),
        }
        self.client.post(self.url, data)
        self.assertEqual(Scenario.objects.count(), 1)

        # missing column in filter fields
        data = {
            "name": "Least Cost Eletrification",
            "vector_dataset": str(self.dataset_1.id),
            "filter_fields": json.dumps(
                [
                    {
                        "label": "Population",
                        "description": "Population in 2025",
                    }
                ]
            ),
            "popup_fields": json.dumps(
                [
                    {
                        "label": "Population",
                        "description": "Population in 2025",
                        "column": "Pop",
                    }
                ]
            ),
        }
        self.client.post(self.url, data)
        self.assertEqual(Scenario.objects.count(), 1)
        # missing label in filter fields
        data = {
            "name": "Least Cost Eletrification",
            "vector_dataset": str(self.dataset_1.id),
            "filter_fields": json.dumps(
                [
                    {
                        "description": "Population in 2025",
                        "column": "Pop",
                    }
                ]
            ),
            "popup_fields": json.dumps(
                [
                    {
                        "label": "Population",
                        "description": "Population in 2025",
                        "column": "Pop",
                    }
                ]
            ),
        }
        self.client.post(self.url, data)
        # missing column in popup_fields
        self.assertEqual(Scenario.objects.count(), 1)
        data = {
            "name": "Least Cost Eletrification",
            "vector_dataset": str(self.dataset_1.id),
            "filter_fields": json.dumps(
                [
                    {
                        "label": "Population",
                        "description": "Population in 2025",
                        "column": "Pop",
                    }
                ]
            ),
            "popup_fields": json.dumps(
                [
                    {
                        "label": "Population",
                        "description": "Population in 2025",
                    }
                ]
            ),
        }
        self.client.post(self.url, data)
        self.assertEqual(Scenario.objects.count(), 1)
        # missing label in popup_fields
        self.assertEqual(Scenario.objects.count(), 1)
        data = {
            "name": "Least Cost Eletrification",
            "vector_dataset": str(self.dataset_1.id),
            "filter_fields": json.dumps(
                [
                    {
                        "label": "Population",
                        "description": "Population in 2025",
                        "column": "Pop",
                    }
                ]
            ),
            "popup_fields": json.dumps(
                [
                    {
                        "description": "Population in 2025",
                        "column": "Pop",
                    }
                ]
            ),
        }
        self.client.post(self.url, data)
        self.assertEqual(Scenario.objects.count(), 1)
