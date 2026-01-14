import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from proenergia.datasets.models import DataModel


class TestScenarioAdmin(TestCase):
    def setUp(self):
        self.superadmin_user = get_user_model().objects.create_superuser(
            username="superadmin",
            email="superadmin@example.com",
            password="testpass123",
        )
        self.url = reverse("admin:datasets_datamodel_add")

    def test_validation(self):
        self.client.login(username="superadmin", password="testpass123")
        data = {
            "name": "Least Cost Eletrification",
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
        self.assertEqual(DataModel.objects.count(), 1)

        # same name
        data = {
            "name": "Least Cost Eletrification",
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
        self.assertEqual(DataModel.objects.count(), 1)
        # missing column in filter fields
        data = {
            "name": "PUE",
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
        self.assertEqual(DataModel.objects.count(), 1)
        # missing label in filter fields
        data = {
            "name": "Clean Cooking",
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
        self.assertEqual(DataModel.objects.count(), 1)
        data = {
            "name": "Another Model",
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
        self.assertEqual(DataModel.objects.count(), 1)
        # missing label in popup_fields
        self.assertEqual(DataModel.objects.count(), 1)
        data = {
            "name": "Least Cost Eletrification 2",
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
        self.assertEqual(DataModel.objects.count(), 1)
