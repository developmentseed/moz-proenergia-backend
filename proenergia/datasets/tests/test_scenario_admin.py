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
            "presentation_order": 2,
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
                        "columns": ["Pop"],
                        "method": "sum",
                        "unit": "individuals",
                        "group_by": "age",
                    },
                    {
                        "label": "Technology by District",
                        "description": "Technology by District",
                        "columns": ["Tech", "District"],
                        "method": "count",
                        "group_by": "age",
                        "chartType": "bar",
                        "category": "Stats",
                        "hasDecimal": True,
                    },
                ]
            ),
            "visualization_column": "Pop",
            "color_coding": json.dumps(
                [
                    {
                        "value": 1000,
                        "color": "#eee3dd",
                    },
                    {
                        "value": 2000,
                        "color": "#333",
                    },
                    {
                        "value": 3000,
                        "color": "#FFF",
                    },
                    {
                        "value": 4000,
                        "color": "#999FFF",
                    },
                ]
            ),
        }
        self.client.post(self.url, data)
        self.assertEqual(DataModel.objects.count(), 1)

        # same name
        data = {
            "name": "Least Cost Electrification",
            "presentation_order": 2,
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
                        "columns": ["Pop"],
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
            "presentation_order": 2,
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
                        "columns": ["Pop"],
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
            "presentation_order": 2,
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
            "presentation_order": 2,
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
            "presentation_order": 2,
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
                        "columns": ["Pop"],
                        "method": "sum",
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
            "presentation_order": 2,
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
                        "columns": ["Pop"],
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
        data["color_coding"] = json.dumps(
            [
                {
                    "value": 1000,
                }
            ]
        )
        self.client.post(self.url, data)
        self.assertEqual(DataModel.objects.count(), 1)

        # invalid color hex code in color_coding
        data["color_coding"] = json.dumps([{"value": 1000, "color": "#455f"}])
        self.client.post(self.url, data)
        self.assertEqual(DataModel.objects.count(), 1)
