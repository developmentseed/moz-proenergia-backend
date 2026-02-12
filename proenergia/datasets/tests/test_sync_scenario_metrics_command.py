from io import StringIO
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from proenergia.datasets.models import (
    DataModel,
    Scenario,
    ScenarioData,
    ScenarioDataMetrics,
    VectorDataset,
)


class TestSyncScenarioMetricsCommand(TestCase):
    def setUp(self):
        # Create user
        self.user = get_user_model().objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )

        # Create dataset
        self.dataset = VectorDataset.objects.create(
            name="Test Dataset",
            created_by=self.user,
            last_updated_by=self.user,
            is_public=True,
            is_approved=True,
        )

        # Create DataModel with summary fields
        self.data_model = DataModel.objects.create(
            name="Test Model",
            summary_fields=[
                {
                    "label": "Cost",
                    "description": "Total cost",
                    "column": "cost",
                    "unit": "USD",
                    "type": "numeric",
                },
                {
                    "label": "Population",
                    "description": "Population count",
                    "column": "population",
                    "unit": "people",
                    "type": "numeric",
                },
                {
                    "label": "Location",
                    "description": "Location name",
                    "column": "location",
                    "unit": "",
                    "type": "string",
                },
                {
                    "label": "Technology",
                    "description": "Technology type",
                    "column": "technology",
                    "unit": "",
                    "type": "string",
                },
            ],
        )

        # Create scenario
        self.scenario = Scenario.objects.create(
            name="Test Scenario", model=self.data_model, vector_dataset=self.dataset
        )

        # Create test data with various scenarios
        self.test_data = [
            {
                "cost": 25000,
                "population": 1500,
                "location": "Maputo",
                "technology": "SHS",
            },
            {
                "cost": 123456.78,
                "population": 2300,
                "location": "Tete",
                "technology": "GridExtension",
            },
            {
                "cost": "45000.5",
                "population": "800",
                "location": "Beira",
                "technology": "MiniGrid",
            },
            {
                "cost": "invalid",
                "population": 1200,
                "location": None,
                "technology": "SHS",
            },
            {
                "cost": 75000,
                "population": None,
                "location": "Nampula",
                "technology": "",
            },
        ]

        # Create ScenarioData records
        for i, data in enumerate(self.test_data, 1):
            ScenarioData.objects.create(
                scenario=self.scenario, feature_id=i, metadata=data
            )

    def test_basic_metrics_creation(self):
        """Test that command creates correct ScenarioDataMetrics records"""
        # Run the command
        out = StringIO()
        call_command("sync_scenario_metrics", scenario_id=self.scenario.id, stdout=out)

        # Check that metrics were created
        metrics = ScenarioDataMetrics.objects.filter(scenario=self.scenario)
        self.assertTrue(metrics.exists())

        # Check specific metrics for feature_id=1
        feature_1_metrics = metrics.filter(feature_id=1)

        # Should have cost (numeric), population (numeric), location (string), technology (string)
        self.assertEqual(feature_1_metrics.count(), 4)

        # Check cost metric
        cost_metric = feature_1_metrics.get(key="cost")
        self.assertEqual(cost_metric.numeric_value, Decimal("25000"))
        self.assertIsNone(cost_metric.string_value)

        # Check location metric
        location_metric = feature_1_metrics.get(key="location")
        self.assertEqual(location_metric.string_value, "Maputo")
        self.assertIsNone(location_metric.numeric_value)

    def test_numeric_value_handling(self):
        """Test numeric value extraction and conversion"""
        call_command("sync_scenario_metrics", scenario_id=self.scenario.id, verbosity=0)

        metrics = ScenarioDataMetrics.objects.filter(scenario=self.scenario, key="cost")

        # Feature 1: integer
        cost_1 = metrics.get(feature_id=1)
        self.assertEqual(cost_1.numeric_value, Decimal("25000"))

        # Feature 2: float
        cost_2 = metrics.get(feature_id=2)
        self.assertEqual(cost_2.numeric_value, Decimal("123456.78"))

        # Feature 3: string number
        cost_3 = metrics.get(feature_id=3)
        self.assertEqual(cost_3.numeric_value, Decimal("45000.5"))

        # Feature 4: invalid numeric value - should not create metric
        self.assertFalse(metrics.filter(feature_id=4).exists())

        # Feature 5: valid number
        cost_5 = metrics.get(feature_id=5)
        self.assertEqual(cost_5.numeric_value, Decimal("75000"))

    def test_string_value_handling(self):
        """Test string value extraction"""
        call_command("sync_scenario_metrics", scenario_id=self.scenario.id, verbosity=0)

        # Test location field
        location_metrics = ScenarioDataMetrics.objects.filter(
            scenario=self.scenario, key="location"
        )

        # Feature 1: normal string
        loc_1 = location_metrics.get(feature_id=1)
        self.assertEqual(loc_1.string_value, "Maputo")

        # Feature 3: string value
        loc_3 = location_metrics.get(feature_id=3)
        self.assertEqual(loc_3.string_value, "Beira")

        # Feature 4: None value - should not create metric
        self.assertFalse(location_metrics.filter(feature_id=4).exists())

        # Test technology field with empty string
        tech_metrics = ScenarioDataMetrics.objects.filter(
            scenario=self.scenario, key="technology"
        )

        # Feature 5: empty string - still creates metric (empty string != None)
        tech_5 = tech_metrics.get(feature_id=5)
        self.assertEqual(tech_5.string_value, "")

    def test_scenario_id_option(self):
        """Test --scenario-id flag targets specific scenario"""
        # Create another scenario
        other_scenario = Scenario.objects.create(
            name="Other Scenario", model=self.data_model, vector_dataset=self.dataset
        )
        ScenarioData.objects.create(
            scenario=other_scenario,
            feature_id=1,
            metadata={"cost": 999, "location": "Other"},
        )

        # Run command for specific scenario only
        call_command("sync_scenario_metrics", scenario_id=self.scenario.id, verbosity=0)

        # Check only our scenario has metrics
        self.assertTrue(
            ScenarioDataMetrics.objects.filter(scenario=self.scenario).exists()
        )
        self.assertFalse(
            ScenarioDataMetrics.objects.filter(scenario=other_scenario).exists()
        )

    def test_invalid_scenario_id(self):
        """Test error handling for invalid scenario ID"""
        out = StringIO()
        call_command("sync_scenario_metrics", scenario_id=999, stdout=out)

        output = out.getvalue()
        self.assertIn("Scenario with ID 999 not found", output)

    def test_clear_option(self):
        """Test --clear flag removes existing metrics"""
        # Create some existing metrics
        ScenarioDataMetrics.objects.create(
            scenario=self.scenario,
            feature_id=99,
            key="old_metric",
            numeric_value=Decimal("123"),
        )

        initial_count = ScenarioDataMetrics.objects.filter(
            scenario=self.scenario
        ).count()
        self.assertEqual(initial_count, 1)

        # Run command with clear
        out = StringIO()
        call_command(
            "sync_scenario_metrics",
            scenario_id=self.scenario.id,
            clear=True,
            stdout=out,
        )

        # Check old metrics were cleared and new ones created
        metrics = ScenarioDataMetrics.objects.filter(scenario=self.scenario)
        self.assertFalse(metrics.filter(key="old_metric").exists())
        self.assertTrue(metrics.filter(key="cost").exists())

        output = out.getvalue()
        self.assertIn("Cleared 1 existing metrics", output)

    def test_no_summary_fields(self):
        """Test behavior when DataModel has no summary_fields"""
        # Create model with no summary fields
        empty_model = DataModel.objects.create(name="Empty Model", summary_fields=[])
        empty_scenario = Scenario.objects.create(
            name="Empty Scenario", model=empty_model, vector_dataset=self.dataset
        )

        out = StringIO()
        call_command("sync_scenario_metrics", scenario_id=empty_scenario.id, stdout=out)

        output = out.getvalue()
        self.assertIn("No summary fields configured", output)

        # No metrics should be created
        self.assertFalse(
            ScenarioDataMetrics.objects.filter(scenario=empty_scenario).exists()
        )

    def test_missing_metadata_fields(self):
        """Test handling when ScenarioData metadata is missing configured fields"""
        # Create scenario data without some configured fields
        ScenarioData.objects.create(
            scenario=self.scenario,
            feature_id=100,
            metadata={"cost": 5000},  # Missing population, location, technology
        )

        call_command("sync_scenario_metrics", scenario_id=self.scenario.id, verbosity=0)

        # Should only create metric for cost
        feature_100_metrics = ScenarioDataMetrics.objects.filter(
            scenario=self.scenario, feature_id=100
        )
        self.assertEqual(feature_100_metrics.count(), 1)
        self.assertEqual(feature_100_metrics.first().key, "cost")

    def test_command_output_messages(self):
        """Test that command produces appropriate output messages"""
        out = StringIO()
        call_command("sync_scenario_metrics", scenario_id=self.scenario.id, stdout=out)

        output = out.getvalue()

        # Check for expected output components
        self.assertIn(f"Processing scenario {self.scenario.id}", output)
        self.assertIn("Numeric fields: cost, population", output)
        self.assertIn("String fields: location, technology", output)
        self.assertIn("Processing 5 records", output)
        self.assertIn("✓ Created", output)
        self.assertIn("✓ Metrics sync completed", output)
