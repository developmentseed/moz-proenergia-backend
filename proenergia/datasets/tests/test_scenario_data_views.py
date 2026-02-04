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

    def test_summary_numeric_field(self):
        """Test summary statistics for numeric field (cost)"""
        url = reverse("datasets:scenario-summary", args=[self.scenario_1.id, "cost"])
        res = self.client.get(url)
        assert res.status_code == 200
        assert res.data.get("key") == "cost"
        assert res.data.get("type") == "numeric"
        assert res.data.get("count") == 11
        assert res.data.get("min") == 2523
        assert res.data.get("max") == 898623
        assert res.data.get("sum") == 1417142.2

    def test_summary_string_field(self):
        """Test summary statistics for string field (location)"""
        url = reverse(
            "datasets:scenario-summary", args=[self.scenario_1.id, "location"]
        )
        res = self.client.get(url)
        assert res.status_code == 200
        assert res.data.get("key") == "location"
        assert res.data.get("type") == "string"
        assert res.data.get("count") == 11
        values = res.data.get("values")
        assert values.get("Maputo") == 6
        assert values.get("Tete") == 3
        assert values.get("Chifunde") == 1
        assert values.get("Mocumba") == 1

    def test_summary_nonexistent_key(self):
        """Test summary with non-existent key"""
        url = reverse(
            "datasets:scenario-summary", args=[self.scenario_1.id, "nonexistent"]
        )
        res = self.client.get(url)
        assert res.status_code == 404
        assert "No data found for key" in res.data.get("error")

    def test_summary_nonexistent_scenario(self):
        """Test summary with non-existent scenario"""
        url = reverse("datasets:scenario-summary", args=[9999, "cost"])
        res = self.client.get(url)
        assert res.status_code == 404

    def test_summary_filters(self):
        """Test summary statistics with filters"""
        url = reverse(
            "datasets:scenario-summary", args=[self.scenario_1.id, "location"]
        )
        res = self.client.get(url, {"q": "cost__min=100000"})
        assert res.status_code == 200
        assert res.data.get("key") == "location"
        assert res.data.get("type") == "string"
        assert res.data.get("count") == 2
        values = res.data.get("values")
        assert values.get("Maputo") == 1
        assert values.get("Tete") == 1

        res = self.client.get(url, {"q": "cost__max=15000"})
        assert res.status_code == 200
        assert res.data.get("key") == "location"
        assert res.data.get("type") == "string"
        assert res.data.get("count") == 4
        values = res.data.get("values")
        assert values.get("Maputo") == 1
        assert values.get("Tete") == 1
        assert values.get("Chifunde") == 1
        assert values.get("Mocumba") == 1

        url = reverse("datasets:scenario-summary", args=[self.scenario_1.id, "cost"])
        res = self.client.get(url, {"q": "location=Maputo"})
        assert res.status_code == 200
        assert res.data.get("key") == "cost"
        assert res.data.get("type") == "numeric"
        assert res.data.get("count") == 6
        assert res.data.get("min") == 2523
        assert res.data.get("max") == 230923.7
        assert res.data.get("sum") == 393115.7

        res = self.client.get(url, {"q": "location__in=Maputo;Mocumba"})
        assert res.status_code == 200
        assert res.data.get("key") == "cost"
        assert res.data.get("type") == "numeric"
        assert res.data.get("count") == 7
        assert res.data.get("min") == 2523
        assert res.data.get("max") == 230923.7
        assert res.data.get("sum") == 399538.7
