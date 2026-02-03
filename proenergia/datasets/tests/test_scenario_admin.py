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
            "name": "Least Cost Electrification",
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
            "summary_fields": json.dumps(
                [
                    {
                        "label": "Population",
                        "description": "Population in 2025",
                        "column": "Pop",
                    }
                ]
            ),
            "visualization_column": "Pop",
            "color_coding": json.dumps(
                [
                    {
                        "value": 1000,
                        "color": "#eee3dd",
                    }
                ]
            ),
        }
        self.client.post(self.url, data)
        self.assertEqual(DataModel.objects.count(), 1)

        # same name
        data = {
            "name": "Least Cost Electrification",
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
            "summary_fields": json.dumps(
                [
                    {
                        "label": "Population",
                        "description": "Population in 2025",
                        "column": "Pop",
                    }
                ]
            ),
            "visualization_column": "Pop",
            "color_coding": json.dumps(
                [
                    {
                        "value": 1000,
                        "color": "#eee3dd",
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
            "summary_fields": json.dumps(
                [
                    {
                        "label": "Population",
                        "description": "Population in 2025",
                        "column": "Pop",
                    }
                ]
            ),
            "visualization_column": "Pop",
            "color_coding": json.dumps(
                [
                    {
                        "value": 1000,
                        "color": "#eee3dd",
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
            "name": "Least Cost Electrification 2",
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

        # missing label in summary_fields
        data = {
            "name": "B",
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
            "summary_fields": json.dumps(
                [
                    {
                        "description": "Population in 2025",
                        "column": "Pop",
                    }
                ]
            ),
            "visualization_column": "Pop",
            "color_coding": json.dumps(
                [
                    {
                        "value": 1000,
                        "color": "#eee3dd",
                    }
                ]
            ),
        }
        self.client.post(self.url, data)
        self.assertEqual(DataModel.objects.count(), 1)

        # missing value in color_coding
        data = {
            "name": "New",
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
            "summary_fields": json.dumps(
                [
                    {
                        "label": "Population",
                        "description": "Population in 2025",
                        "column": "Pop",
                    }
                ]
            ),
            "visualization_column": "Pop",
            "color_coding": json.dumps(
                [
                    {
                        "color": "#eee3dd",
                    }
                ]
            ),
        }
        self.client.post(self.url, data)
        self.assertEqual(DataModel.objects.count(), 1)

        # missing color key in color_coding
        data["color_coding"] = [
            {
                "value": 1000,
            }
        ]
        self.client.post(self.url, data)
        self.assertEqual(DataModel.objects.count(), 1)
