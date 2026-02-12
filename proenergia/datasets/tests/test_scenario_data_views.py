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


class TestMultiFieldSummaryView(APITestCase):
    def setUp(self):
        self.superadmin = get_user_model().objects.create_superuser(
            username="superadmin", email="admin@example.com", password="testpass123"
        )

        # Create dataset
        self.dataset = VectorDataset.objects.create(
            name="Test Dataset",
            created_by=self.superadmin,
            last_updated_by=self.superadmin,
            is_public=True,
            is_approved=True,
        )

        # Create model with proper summary_fields
        self.model = DataModel.objects.create(
            name="Test Model",
            summary_fields=[
                {"column": "cost", "type": "numeric", "label": "Cost"},
                {"column": "population", "type": "numeric", "label": "Population"},
                {"column": "location", "type": "string", "label": "Location"},
                {"column": "technology", "type": "string", "label": "Technology"},
                {"column": "district", "type": "string", "label": "District"},
            ],
        )

        # Create scenario
        self.scenario = Scenario.objects.create(
            name="Test Scenario", model=self.model, vector_dataset=self.dataset
        )

        # Create test data
        self.test_data = {
            1: {
                "cost": 23423,
                "population": 1500,
                "location": "Maputo",
                "technology": "SHS",
                "district": "Central",
            },
            2: {
                "cost": 12334.5,
                "population": 2300,
                "location": "Chifunde",
                "technology": "GridExtension",
                "district": "Norte",
            },
            3: {
                "cost": 230923.7,
                "population": 45000,
                "location": "Maputo",
                "technology": "ExistingGrid",
                "district": "Central",
            },
            4: {
                "cost": 23093,
                "population": 1200,
                "location": "Maputo",
                "technology": "SHS",
                "district": "Central",
            },
            5: {
                "cost": 2523,
                "population": 800,
                "location": "Maputo",
                "technology": "SHS",
                "district": "Sul",
            },
            6: {
                "cost": 63423,
                "population": 3400,
                "location": "Maputo",
                "technology": "GridExtension",
                "district": "Central",
            },
            7: {
                "cost": 93423,
                "population": 5600,
                "location": "Tete",
                "technology": "MiniGrid_PV",
                "district": "Norte",
            },
            8: {
                "cost": 6423,
                "population": 450,
                "location": "Mocumba",
                "technology": "SHS",
                "district": "Sul",
            },
            9: {
                "cost": 13223,
                "population": 890,
                "location": "Tete",
                "technology": "SHS",
                "district": "Norte",
            },
            10: {
                "cost": 898623,
                "population": 78000,
                "location": "Tete",
                "technology": "ExistingGrid",
                "district": "Norte",
            },
            11: {
                "cost": 49730,
                "population": 2100,
                "location": "Maputo",
                "technology": "MiniGrid_PV",
                "district": "Central",
            },
        }

        # Create metrics
        from proenergia.datasets.tests.test_helpers import create_scenario_metrics

        create_scenario_metrics(self.scenario, self.test_data)

    def test_single_numeric_field(self):
        """Test summary for a single numeric field"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(url, {"fields": "cost"})

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["scenario_id"], self.scenario.id)
        self.assertIn("cost", data["summaries"])

        cost_summary = data["summaries"]["cost"]
        self.assertEqual(cost_summary["type"], "numeric")
        self.assertEqual(cost_summary["count"], 11)
        self.assertEqual(cost_summary["min"], 2523)
        self.assertEqual(cost_summary["max"], 898623)
        self.assertAlmostEqual(cost_summary["sum"], 1417142.2, places=1)

    def test_single_string_field(self):
        """Test summary for a single string field"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(url, {"fields": "location"})

        self.assertEqual(res.status_code, 200)
        data = res.json()

        location_summary = data["summaries"]["location"]
        self.assertEqual(location_summary["type"], "string")
        self.assertEqual(location_summary["count"], 11)
        self.assertEqual(location_summary["values"]["Maputo"], 6)
        self.assertEqual(location_summary["values"]["Tete"], 3)
        self.assertEqual(location_summary["values"]["Chifunde"], 1)
        self.assertEqual(location_summary["values"]["Mocumba"], 1)

    def test_multiple_fields(self):
        """Test summary for multiple fields"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(url, {"fields": "cost,location,technology"})

        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("cost", data["summaries"])
        self.assertIn("location", data["summaries"])
        self.assertIn("technology", data["summaries"])

        # Check technology distribution
        tech_summary = data["summaries"]["technology"]
        self.assertEqual(tech_summary["values"]["SHS"], 5)
        self.assertEqual(tech_summary["values"]["GridExtension"], 2)
        self.assertEqual(tech_summary["values"]["ExistingGrid"], 2)
        self.assertEqual(tech_summary["values"]["MiniGrid_PV"], 2)

    def test_filters(self):
        """Test summaries with filters"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(url, {"fields": "cost", "q": "location=Maputo"})

        self.assertEqual(res.status_code, 200)
        data = res.json()

        cost_summary = data["summaries"]["cost"]
        self.assertEqual(cost_summary["count"], 6)
        self.assertEqual(cost_summary["min"], 2523)
        self.assertEqual(cost_summary["max"], 230923.7)

    def test_multiple_filters(self):
        """Test summaries with multiple filters"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(
            url, {"fields": "population", "q": "location=Maputo,cost__min=20000"}
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()

        pop_summary = data["summaries"]["population"]
        self.assertEqual(pop_summary["count"], 5)  # Should match rows 1,3,4,6,11

    def test_group_by_single_field(self):
        """Test group_by with a single field"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(url, {"fields": "cost", "group_by": "technology"})

        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["group_by"], "technology")
        cost_summary = data["summaries"]["cost"]
        self.assertIn("grouped", cost_summary)

        # Check SHS group
        shs_group = cost_summary["grouped"]["SHS"]
        self.assertEqual(shs_group["count"], 5)
        self.assertEqual(shs_group["min"], 2523)

        # Check ExistingGrid group
        grid_group = cost_summary["grouped"]["ExistingGrid"]
        self.assertEqual(grid_group["count"], 2)
        self.assertEqual(grid_group["max"], 898623)

    def test_group_by_with_filters(self):
        """Test group_by combined with filters"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(
            url,
            {"fields": "population", "group_by": "technology", "q": "district=Central"},
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()

        pop_summary = data["summaries"]["population"]
        # Should only include rows with district=Central
        self.assertEqual(pop_summary["count"], 5)  # rows 1,3,4,6,11

        # Check grouped results
        shs_group = pop_summary["grouped"]["SHS"]
        self.assertEqual(shs_group["count"], 2)  # rows 1,4

    def test_group_by_string_field(self):
        """Test string field summary with group_by"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(url, {"fields": "district", "group_by": "technology"})

        self.assertEqual(res.status_code, 200)
        data = res.json()

        district_summary = data["summaries"]["district"]
        self.assertIn("grouped", district_summary)

        shs_group = district_summary["grouped"]["SHS"]
        self.assertEqual(shs_group["values"]["Central"], 2)
        self.assertEqual(shs_group["values"]["Sul"], 2)
        self.assertEqual(shs_group["values"]["Norte"], 1)

    def test_missing_fields_parameter(self):
        """Test error when fields parameter is missing"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(url)

        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.json())
        self.assertIn("fields", res.json()["error"])

    def test_invalid_field(self):
        """Test error when requesting invalid field"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(url, {"fields": "cost,invalid_field"})

        self.assertEqual(res.status_code, 400)
        self.assertIn("invalid_field", res.json()["error"])

    def test_invalid_group_by(self):
        """Test error when group_by field is invalid"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(url, {"fields": "cost", "group_by": "invalid_field"})

        self.assertEqual(res.status_code, 400)
        self.assertIn("invalid_field", res.json()["error"])

    def test_numeric_group_by(self):
        """Test error when trying to group by numeric field"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(url, {"fields": "cost", "group_by": "population"})

        self.assertEqual(res.status_code, 400)
        self.assertIn("must be a string field", res.json()["error"])
