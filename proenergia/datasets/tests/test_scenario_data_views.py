from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase

from proenergia.datasets.tasks import import_scenario_data_csv

from ..models import (
    DataModel,
    Scenario,
    ScenarioData,
    ScenarioDataMetrics,
    ScenarioFile,
    VectorDataset,
    VectorFile,
)


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

        # Create model with proper summary_fields using realistic structure
        self.model = DataModel.objects.create(
            name="Test Model",
            summary_fields=[
                {
                    "label": "Population",
                    "description": "Population metrics",
                    "columns": ["Pop2030"],
                    "method": "sum",
                    "group_by": "district",
                },
                {
                    "label": "Total Cost",
                    "description": "Combined cost metrics",
                    "columns": ["InvestmentGen", "additional_cost"],
                    "method": "sum",
                    "unit": "USD",
                },
                {
                    "label": "Technology Distribution",
                    "description": "Technology type distribution",
                    "columns": ["Technology2030"],
                    "method": "count",
                },
                {
                    "label": "Location",
                    "description": "Location information",
                    "columns": ["location"],
                    "method": "count",
                },
            ],
        )

        # Create scenario
        self.scenario = Scenario.objects.create(
            name="Test Scenario", model=self.model, vector_dataset=self.dataset
        )

        # Create test data using realistic column names
        self.test_data = {
            1: {
                "InvestmentGen": 23423,
                "Pop2030": 1500,
                "location": "Maputo",
                "Technology2030": "SHS",
                "district": "Central",
                "additional_cost": 1000,
            },
            2: {
                "InvestmentGen": 12334.5,
                "Pop2030": 2300,
                "location": "Chifunde",
                "Technology2030": "GridExtension",
                "district": "Norte",
                "additional_cost": 500,
            },
            3: {
                "InvestmentGen": 230923.7,
                "Pop2030": 45000,
                "location": "Maputo",
                "Technology2030": "ExistingGrid",
                "district": "Central",
                "additional_cost": 2000,
            },
            4: {
                "InvestmentGen": 23093,
                "Pop2030": 1200,
                "location": "Maputo",
                "Technology2030": "SHS",
                "district": "Central",
                "additional_cost": 800,
            },
            5: {
                "InvestmentGen": 2523,
                "Pop2030": 800,
                "location": "Maputo",
                "Technology2030": "SHS",
                "district": "Sul",
                "additional_cost": 300,
            },
            6: {
                "InvestmentGen": 63423,
                "Pop2030": 3400,
                "location": "Maputo",
                "Technology2030": "GridExtension",
                "district": "Central",
                "additional_cost": 1200,
            },
            7: {
                "InvestmentGen": 93423,
                "Pop2030": 5600,
                "location": "Tete",
                "Technology2030": "MiniGrid_PV",
                "district": "Norte",
                "additional_cost": 1800,
            },
            8: {
                "InvestmentGen": 6423,
                "Pop2030": 450,
                "location": "Mocumba",
                "Technology2030": "SHS",
                "district": "Sul",
                "additional_cost": 200,
            },
            9: {
                "InvestmentGen": 13223,
                "Pop2030": 890,
                "location": "Tete",
                "Technology2030": "SHS",
                "district": "Norte",
                "additional_cost": 400,
            },
            10: {
                "InvestmentGen": 898623,
                "Pop2030": 78000,
                "location": "Tete",
                "Technology2030": "ExistingGrid",
                "district": "Norte",
                "additional_cost": 5000,
            },
            11: {
                "InvestmentGen": 49730,
                "Pop2030": 2100,
                "location": "Maputo",
                "Technology2030": "MiniGrid_PV",
                "district": "Central",
                "additional_cost": 900,
            },
        }

        # Create ScenarioData records from test data
        for feature_id, data in self.test_data.items():
            ScenarioData.objects.create(
                scenario=self.scenario, feature_id=feature_id, metadata=data
            )

        # Sync metrics to populate metric_field_types and create ScenarioDataMetrics
        from proenergia.datasets.utils import sync_scenario_metrics_with_types

        sync_scenario_metrics_with_types(self.scenario)

    def test_single_numeric_field(self):
        """Test summary for a single numeric field"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(url, {"fields": "InvestmentGen"})

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["scenario_id"], self.scenario.id)
        self.assertIn("InvestmentGen", data["summaries"])

        cost_summary = data["summaries"]["InvestmentGen"]
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
        res = self.client.get(url, {"fields": "InvestmentGen,location,Technology2030"})

        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("InvestmentGen", data["summaries"])
        self.assertIn("location", data["summaries"])
        self.assertIn("Technology2030", data["summaries"])

        # Check technology distribution
        tech_summary = data["summaries"]["Technology2030"]
        self.assertEqual(tech_summary["values"]["SHS"], 5)
        self.assertEqual(tech_summary["values"]["GridExtension"], 2)
        self.assertEqual(tech_summary["values"]["ExistingGrid"], 2)
        self.assertEqual(tech_summary["values"]["MiniGrid_PV"], 2)

    def test_filters(self):
        """Test summaries with filters"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(url, {"fields": "InvestmentGen", "q": "location=Maputo"})

        self.assertEqual(res.status_code, 200)
        data = res.json()

        cost_summary = data["summaries"]["InvestmentGen"]
        self.assertEqual(cost_summary["count"], 6)
        self.assertEqual(cost_summary["min"], 2523)
        self.assertEqual(cost_summary["max"], 230923.7)

    def test_multiple_filters(self):
        """Test summaries with multiple filters"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(
            url, {"fields": "Pop2030", "q": "location=Maputo,InvestmentGen__min=20000"}
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()

        pop_summary = data["summaries"]["Pop2030"]
        self.assertEqual(pop_summary["count"], 5)  # Should match rows 1,3,4,6,11

    def test_group_by_single_field(self):
        """Test group_by with a single field"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(
            url, {"fields": "InvestmentGen", "group_by": "Technology2030"}
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["group_by"], "Technology2030")
        cost_summary = data["summaries"]["InvestmentGen"]
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
            {
                "fields": "Pop2030",
                "group_by": "Technology2030",
                "q": "district=Central",
            },
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()

        pop_summary = data["summaries"]["Pop2030"]
        # Should only include rows with district=Central
        self.assertEqual(pop_summary["count"], 5)  # rows 1,3,4,6,11

        # Check grouped results
        shs_group = pop_summary["grouped"]["SHS"]
        self.assertEqual(shs_group["count"], 2)  # rows 1,4

    def test_group_by_string_field(self):
        """Test string field summary with group_by"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(url, {"fields": "district", "group_by": "Technology2030"})

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
        """Test that invalid fields return 200 with count=0"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(url, {"fields": "InvestmentGen,invalid_field"})

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("invalid_field", data["summaries"])
        self.assertEqual(data["summaries"]["invalid_field"]["count"], 0)
        # Valid field should still work
        self.assertIn("InvestmentGen", data["summaries"])
        self.assertEqual(data["summaries"]["InvestmentGen"]["count"], 11)

    def test_invalid_group_by(self):
        """Test error when group_by field is invalid"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(
            url, {"fields": "InvestmentGen", "group_by": "invalid_field"}
        )

        self.assertEqual(res.status_code, 400)
        self.assertIn("invalid_field", res.json()["error"])

    def test_numeric_group_by(self):
        """Test error when trying to group by numeric field"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(url, {"fields": "InvestmentGen", "group_by": "Pop2030"})

        self.assertEqual(res.status_code, 400)
        self.assertIn("must be a string field", res.json()["error"])

    def test_field_without_data(self):
        """Test that valid fields without data return 200 with count=0"""
        # Add a new field to the model configuration that has no data
        self.model.metric_field_types["EmptyField"] = "numeric"
        self.model.save()

        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(url, {"fields": "EmptyField,InvestmentGen"})

        self.assertEqual(res.status_code, 200)
        data = res.json()

        # EmptyField should have count=0
        self.assertIn("EmptyField", data["summaries"])
        self.assertEqual(data["summaries"]["EmptyField"]["count"], 0)

        # InvestmentGen should still work normally
        self.assertIn("InvestmentGen", data["summaries"])
        self.assertEqual(data["summaries"]["InvestmentGen"]["count"], 11)

    def test_multiple_invalid_and_missing_fields(self):
        """Test mixed valid, invalid, and no-data fields all return 200"""
        # Add a configured field with no data
        self.model.metric_field_types["NoDataField"] = "string"
        self.model.save()

        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(
            url,
            {
                "fields": "InvestmentGen,invalid_field1,NoDataField,invalid_field2,location"
            },
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Check all fields are present in response
        self.assertIn("InvestmentGen", data["summaries"])
        self.assertIn("invalid_field1", data["summaries"])
        self.assertIn("NoDataField", data["summaries"])
        self.assertIn("invalid_field2", data["summaries"])
        self.assertIn("location", data["summaries"])

        # Invalid fields should have count=0
        self.assertEqual(data["summaries"]["invalid_field1"]["count"], 0)
        self.assertEqual(data["summaries"]["invalid_field2"]["count"], 0)

        # No data field should have count=0
        self.assertEqual(data["summaries"]["NoDataField"]["count"], 0)

        # Valid fields with data should work normally
        self.assertEqual(data["summaries"]["InvestmentGen"]["count"], 11)
        self.assertEqual(data["summaries"]["location"]["count"], 11)

    def test_filters_resulting_in_no_data(self):
        """Test that filters resulting in no data return count=0, not 404"""
        url = reverse("datasets:scenario-summaries", args=[self.scenario.id])
        res = self.client.get(
            url, {"fields": "InvestmentGen", "q": "location=NonExistentLocation"}
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Should have count=0 when filter results in no data
        self.assertIn("InvestmentGen", data["summaries"])
        self.assertEqual(data["summaries"]["InvestmentGen"]["count"], 0)
