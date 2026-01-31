from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase

from proenergia.datasets.tasks import import_scenario_data_csv

from ..models import DataModel, Scenario, ScenarioFile, VectorDataset, VectorFile


class TestScenarioDataDetailViews(APITestCase):
    @patch("proenergia.datasets.tasks.import_scenario_data_csv.delay")
    @patch("proenergia.datasets.tasks.generate_pmtiles.delay")
    @patch("proenergia.datasets.tasks.generate_scenario_pmtiles.delay")
    def setUp(self, mock_1, mock_2, mock_3):
        self.scenario_csv = "./proenergia/datasets/fixtures/scenario.csv"
        self.superadmin = get_user_model().objects.create_superuser(
            username="superadmin", email="admin@example.com", password="testpass123"
        )
        self.dataset_1 = VectorDataset.objects.create(
            name="Boundaries",
            description="Administratives Boundaries",
            source="OSM",
            is_public=True,
            is_approved=True,
            created_by=self.superadmin,
            last_updated_by=self.superadmin,
        )
        file = SimpleUploadedFile(
            "old.geojson", b"file_content", content_type="application/json"
        )
        self.vector_file_1 = VectorFile.objects.create(
            dataset=self.dataset_1,
            file=file,
            created_by=self.superadmin,
            status="ready",
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
        )
        self.scenario_1 = Scenario.objects.create(
            name="Least Cost Electrification",
            vector_dataset=self.dataset_1,
            model=self.model_1,
        )
        with open(self.scenario_csv, "rb") as f:
            file_content = f.read()

        scenario_file = SimpleUploadedFile(
            "scenario.csv", file_content, content_type="text/csv"
        )
        self.scenario_file_1 = ScenarioFile.objects.create(
            scenario=self.scenario_1,
            file=scenario_file,
            created_by=self.superadmin,
            status="ready",
        )
        import_scenario_data_csv(self.scenario_file_1.id)

    def test_feature_detail(self):
        url = reverse("datasets:feature-detail", args=[self.scenario_1.id, 1])
        res = self.client.get(url)
        assert res.status_code == 200
        assert res.data.get("feature_id") == 1
        assert res.data.get("cost") == 23423
        assert res.data.get("location") == "Maputo"
        assert res.data.get("country") == "Mozambique"

        url = reverse("datasets:feature-detail", args=[self.scenario_1.id, 2])
        res = self.client.get(url)
        assert res.status_code == 200
        assert res.data.get("feature_id") == 2
        assert res.data.get("cost") == 12334.5
        assert res.data.get("location") == "Chifunde"
        assert res.data.get("country") == "Mozambique"
