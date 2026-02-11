from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import DataModel, Scenario, ScenarioFile, VectorDataset, VectorFile


class TestDataModelViews(APITestCase):
    @patch("proenergia.datasets.tasks.generate_scenario_pmtiles.delay")
    @patch("proenergia.datasets.tasks.generate_pmtiles.delay")
    def setUp(self, mock_1, mock_2):
        # Clean up any leftover files from previous test runs
        ScenarioFile.objects.all().delete()
        self.superadmin_user = get_user_model().objects.create_superuser(
            username="superadmin",
            email="superadmin@example.com",
            password="testpass123",
        )
        self.admin_user = get_user_model().objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            is_staff=True,
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
        file = SimpleUploadedFile(
            "old.geojson", b"file_content", content_type="application/json"
        )
        self.vector_file_1 = VectorFile.objects.create(
            dataset=self.dataset_1,
            file=file,
            created_by=self.superadmin_user,
            status="ready",
        )
        self.dataset_2 = VectorDataset.objects.create(
            name="Population Clusters",
            is_public=True,
            is_approved=True,
            created_by=self.superadmin_user,
            last_updated_by=self.superadmin_user,
        )
        self.model_1 = DataModel.objects.create(
            name="PUE",
            filter_fields=[
                {
                    "label": "Population",
                    "description": "Population in 2025",
                    "column": "Pop",
                }
            ],
            popup_fields=[
                {
                    "label": "Population",
                    "description": "Population in 2025",
                    "column": "Pop",
                }
            ],
            summary_fields=[
                {
                    "label": "Population",
                    "description": "Population in 2025",
                    "columns": ["Pop"],
                    "method": "count",
                    "unit": "individuals",
                    "group_by": "sex",
                }
            ],
            visualization_column="Pop",
            color_coding=[
                {"value": 1000, "color": "#ddd"},
                {"value": 10000, "color": "#ff00dd"},
            ],
        )
        self.model_2 = DataModel.objects.create(
            name="Clean Cooking",
            filter_fields=[
                {
                    "label": "Population",
                    "description": "Population in 2025",
                    "column": "Pop",
                },
                {
                    "label": "State",
                    "description": "State name",
                    "column": "State",
                },
            ],
            popup_fields=[
                {
                    "label": "Population",
                    "description": "Population in 2025",
                    "column": "Pop",
                }
            ],
        )
        self.scenario_1 = Scenario.objects.create(
            name="Least Cost Electrification",
            vector_dataset=self.dataset_1,
            model=self.model_1,
        )
        self.scenario_2 = Scenario.objects.create(
            name="Clean Cooking 1",
            vector_dataset=self.dataset_2,
            model=self.model_2,
        )
        file = SimpleUploadedFile(
            "old.csv", b"id,col_b\n1,blah", content_type="text/csv"
        )
        self.scenario_file_1 = ScenarioFile.objects.create(
            scenario=self.scenario_1,
            file=file,
            created_by=self.superadmin_user,
            status="ready",
        )
        file = SimpleUploadedFile(
            "new.csv", b"id,col_b\n1,blah", content_type="text/csv"
        )
        self.scenario_file_2 = ScenarioFile.objects.create(
            scenario=self.scenario_2,
            file=file,
            created_by=self.superadmin_user,
            status="ready",
        )
        self.url = reverse("datasets:model-list")

    @patch("proenergia.datasets.tasks.generate_scenario_pmtiles.delay")
    def test_model_list_unauthenticated(self, mock_task):
        req = self.client.get(self.url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 2
        assert req.data.get("results")[0]["name"] == "PUE"
        assert req.data.get("results")[1]["name"] == "Clean Cooking"
        assert (
            req.data.get("results")[0]["scenarios"][0]["name"]
            == "Least Cost Electrification"
        )
        assert req.data.get("results")[1]["scenarios"][0]["name"] == "Clean Cooking 1"
        assert req.data.get("results")[0]["scenarios"][0]["model_file"].startswith(
            "scenarios/least-cost-electrification_v1"
        )
        assert req.data.get("results")[1]["scenarios"][0]["model_file"].startswith(
            "scenarios/clean-cooking-1_v1"
        )
        assert req.data.get("results")[0]["filter_fields"] == [
            {
                "label": "Population",
                "description": "Population in 2025",
                "column": "Pop",
            }
        ]
        assert req.data.get("results")[1]["filter_fields"] == [
            {
                "label": "Population",
                "description": "Population in 2025",
                "column": "Pop",
            },
            {"label": "State", "description": "State name", "column": "State"},
        ]
        assert req.data.get("results")[0]["popup_fields"] == [
            {
                "label": "Population",
                "description": "Population in 2025",
                "column": "Pop",
            }
        ]
        assert req.data.get("results")[1]["popup_fields"] == [
            {
                "label": "Population",
                "description": "Population in 2025",
                "column": "Pop",
            }
        ]
        assert req.data.get("results")[0]["summary_fields"] == [
            {
                "label": "Population",
                "description": "Population in 2025",
                "columns": ["Pop"],
                "method": "count",
                "unit": "individuals",
                "group_by": "sex",
            }
        ]
        assert req.data.get("results")[0]["visualization_column"] == "Pop"
        assert req.data.get("results")[0]["color_coding"] == [
            {"value": 1000, "color": "#ddd"},
            {"value": 10000, "color": "#ff00dd"},
        ]

    @patch("proenergia.datasets.tasks.generate_scenario_pmtiles.delay")
    def test_model_detail_unauthenticated(self, mock_task):
        url = reverse("datasets:model-detail", args=[self.model_1.id])
        # upload files again
        file = SimpleUploadedFile(
            "old.csv", b"id,col_b\n1,blah", content_type="text/csv"
        )
        self.scenario_file_1 = ScenarioFile.objects.create(
            scenario=self.scenario_1,
            file=file,
            created_by=self.superadmin_user,
            status="ready",
        )
        file = SimpleUploadedFile(
            "new.csv", b"id,col_b\n1,blah", content_type="text/csv"
        )
        self.scenario_file_2 = ScenarioFile.objects.create(
            scenario=self.scenario_2,
            file=file,
            created_by=self.superadmin_user,
            status="ready",
        )
        # execute request
        req = self.client.get(url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("name") == "PUE"
        assert req.data["scenarios"][0]["name"] == "Least Cost Electrification"
        assert (
            req.data["scenarios"][0]["model_file"]
            == "scenarios/least-cost-electrification_v2.csv"
        )

        url = reverse("datasets:model-detail", args=[self.model_2.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("name") == "Clean Cooking"
        assert req.data["scenarios"][0]["name"] == "Clean Cooking 1"
        assert (
            req.data["scenarios"][0]["model_file"] == "scenarios/clean-cooking-1_v2.csv"
        )

    def tearDown(self):
        ScenarioFile.objects.all().delete()
