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

        # Create DataModel with summary fields using realistic column names
        self.data_model = DataModel.objects.create(
            name="Test Model",
            summary_fields=[
                {
                    "label": "Population 2030",
                    "description": "Total population by 2030",
                    "columns": ["Pop2030"],
                    "unit": "people",
                    "method": "sum",
                    "group_by": "Technology2030",
                },
                {
                    "label": "Total Investment",
                    "description": "Combined infrastructure investment",
                    "columns": ["InvestmentGen", "InvestmentDist"],
                    "unit": "USD",
                    "method": "sum",
                    "group_by": "Technology2030",
                },
                {
                    "label": "New Connections",
                    "description": "Total new household connections",
                    "columns": ["NewHHConnectionsTotal"],
                    "unit": "connections",
                    "method": "sum",
                    "group_by": "Technology2030",
                },
                {
                    "label": "Average LCOE",
                    "description": "Average levelized cost of electricity",
                    "columns": ["LCOETotal"],
                    "unit": "USD/kWh",
                    "method": "average",
                    "group_by": "Technology2030",
                },
                {
                    "label": "Distribution Infrastructure",
                    "description": "MV and LV line kilometers",
                    "columns": ["MV_km_Total", "LV_km_Total"],
                    "unit": "km",
                    "method": "sum",
                },
            ],
        )

        # Create scenario
        self.scenario = Scenario.objects.create(
            name="Test Scenario", model=self.data_model, vector_dataset=self.dataset
        )

        # Create test data with realistic column names and values
        self.test_data = [
            {
                "Pop2030": 1500,
                "Technology2030": "GridExtension",
                "InvestmentGen": 45000.0,
                "InvestmentDist": 12000.0,
                "NewHHConnectionsTotal": 280,
                "LCOETotal": 0.085,
                "MV_km_Total": 2.5,
                "LV_km_Total": 8.3,
            },
            {
                "Pop2030": 2300,
                "Technology2030": "MiniGrid_PV",
                "InvestmentGen": 125000.0,
                "InvestmentDist": 35000.0,
                "NewHHConnectionsTotal": 420,
                "LCOETotal": 0.142,
                "MV_km_Total": 0.0,
                "LV_km_Total": 12.7,
            },
            {
                "Pop2030": "850",  # String number to test type inference
                "Technology2030": "SHS",
                "InvestmentGen": "8500.0",  # String number
                "InvestmentDist": 0.0,
                "NewHHConnectionsTotal": 155,
                "LCOETotal": "0.225",
                "MV_km_Total": 0,
                "LV_km_Total": 0,
            },
            {
                "Pop2030": 950,
                "Technology2030": "ExistingGrid",
                "InvestmentGen": 0,
                "InvestmentDist": "invalid",  # Invalid value to test robustness
                "NewHHConnectionsTotal": 0,
                "LCOETotal": 0.075,
                "MV_km_Total": None,  # Missing value
                "LV_km_Total": 5.2,
            },
            {
                "Pop2030": 1100,
                "Technology2030": "MiniGrid_Diesel",
                "InvestmentGen": 65000,
                "InvestmentDist": None,  # Missing value
                "NewHHConnectionsTotal": 200,
                "LCOETotal": 0.195,
                "MV_km_Total": 1.5,
                "LV_km_Total": 9.8,
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

        # Should have multiple numeric and string metrics based on the test data
        self.assertGreater(feature_1_metrics.count(), 0)

        # Check Pop2030 metric (numeric)
        pop_metric = feature_1_metrics.get(key="Pop2030")
        self.assertEqual(pop_metric.numeric_value, Decimal("1500"))
        self.assertIsNone(pop_metric.string_value)

        # Check Technology2030 metric (string)
        tech_metric = feature_1_metrics.get(key="Technology2030")
        self.assertEqual(tech_metric.string_value, "GridExtension")
        self.assertIsNone(tech_metric.numeric_value)

    def test_numeric_value_handling(self):
        """Test numeric value extraction and conversion"""
        call_command("sync_scenario_metrics", scenario_id=self.scenario.id, verbosity=0)

        metrics = ScenarioDataMetrics.objects.filter(
            scenario=self.scenario, key="Pop2030"
        )

        # Feature 1: Pop2030 = 1500
        pop_1 = metrics.get(feature_id=1, key="Pop2030")
        self.assertEqual(pop_1.numeric_value, Decimal("1500"))

        # Feature 2: Pop2030 = 2300
        pop_2 = metrics.get(feature_id=2, key="Pop2030")
        self.assertEqual(pop_2.numeric_value, Decimal("2300"))

        # Feature 3: Pop2030 = "850" (string number)
        pop_3 = metrics.get(feature_id=3, key="Pop2030")
        self.assertEqual(pop_3.numeric_value, Decimal("850"))

        # Feature 4: InvestmentDist = "invalid" - should not create metric for InvestmentDist
        invalid_metrics = metrics.filter(feature_id=4, key="InvestmentDist")
        self.assertFalse(invalid_metrics.exists())

        # Feature 5: Pop2030 = 1100
        pop_5 = metrics.get(feature_id=5, key="Pop2030")
        self.assertEqual(pop_5.numeric_value, Decimal("1100"))

    def test_string_value_handling(self):
        """Test string value extraction"""
        call_command("sync_scenario_metrics", scenario_id=self.scenario.id, verbosity=0)

        # Test Technology2030 field
        tech_metrics = ScenarioDataMetrics.objects.filter(
            scenario=self.scenario, key="Technology2030"
        )

        # Feature 1: GridExtension
        tech_1 = tech_metrics.get(feature_id=1)
        self.assertEqual(tech_1.string_value, "GridExtension")

        # Feature 2: MiniGrid_PV
        tech_2 = tech_metrics.get(feature_id=2)
        self.assertEqual(tech_2.string_value, "MiniGrid_PV")

        # Feature 3: SHS
        tech_3 = tech_metrics.get(feature_id=3)
        self.assertEqual(tech_3.string_value, "SHS")

        # Feature 4: ExistingGrid
        tech_4 = tech_metrics.get(feature_id=4)
        self.assertEqual(tech_4.string_value, "ExistingGrid")

        # Feature 5: MiniGrid_Diesel
        tech_5 = tech_metrics.get(feature_id=5)
        self.assertEqual(tech_5.string_value, "MiniGrid_Diesel")

    def test_scenario_id_option(self):
        """Test --scenario-id flag targets specific scenario"""
        # Create another scenario
        other_scenario = Scenario.objects.create(
            name="Other Scenario", model=self.data_model, vector_dataset=self.dataset
        )
        ScenarioData.objects.create(
            scenario=other_scenario,
            feature_id=1,
            metadata={"Pop2030": 999, "Technology2030": "Other"},
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

    def test_clears_existing_metrics(self):
        """Test that sync clears existing metrics before creating new ones"""
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

        # Run command
        call_command(
            "sync_scenario_metrics",
            scenario_id=self.scenario.id,
            verbosity=0,
        )

        # Check old metrics were cleared and new ones created
        metrics = ScenarioDataMetrics.objects.filter(scenario=self.scenario)
        self.assertFalse(metrics.filter(key="old_metric").exists())
        self.assertTrue(metrics.filter(key="Pop2030").exists())

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
        self.assertIn("Fields synced: 0", output)

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
            metadata={"Pop2030": 5000},  # Missing other configured fields
        )

        call_command("sync_scenario_metrics", scenario_id=self.scenario.id, verbosity=0)

        # Should only create metric for Pop2030
        feature_100_metrics = ScenarioDataMetrics.objects.filter(
            scenario=self.scenario, feature_id=100
        )
        self.assertEqual(feature_100_metrics.count(), 1)
        self.assertEqual(feature_100_metrics.first().key, "Pop2030")

    def test_command_output_messages(self):
        """Test that command produces appropriate output messages"""
        out = StringIO()
        call_command("sync_scenario_metrics", scenario_id=self.scenario.id, stdout=out)

        output = out.getvalue()

        # Check for expected output components
        self.assertIn(f"Processing scenario {self.scenario.id}", output)
        self.assertIn("Fields synced:", output)
        self.assertIn("Numeric fields:", output)
        self.assertIn("String fields:", output)
        self.assertIn("✓ Created", output)
        self.assertIn("✓ Metrics sync completed", output)

    def test_metric_field_types_populated(self):
        """Test that metric_field_types is populated after sync"""
        # Initially should be empty
        self.assertEqual(self.data_model.metric_field_types, {})

        # Run sync
        call_command("sync_scenario_metrics", scenario_id=self.scenario.id, verbosity=0)

        # Refresh from DB
        self.data_model.refresh_from_db()

        # Check metric_field_types has been populated correctly
        # Should include all columns from multi-column fields and group_by columns
        actual_types = self.data_model.metric_field_types

        # Must include all these fields
        required_fields = {
            "Pop2030": "numeric",
            "InvestmentGen": "numeric",
            "NewHHConnectionsTotal": "numeric",
            "LCOETotal": "numeric",
            "MV_km_Total": "numeric",
            "LV_km_Total": "numeric",
        }

        for field, expected_type in required_fields.items():
            self.assertIn(
                field, actual_types, f"Field {field} should be in metric_field_types"
            )
            self.assertEqual(
                actual_types[field],
                expected_type,
                f"Field {field} should be {expected_type}",
            )

        # InvestmentDist might be string due to "invalid" value in test data
        self.assertIn("InvestmentDist", actual_types)
        # Technology2030 should be included as it's used as group_by
        self.assertIn("Technology2030", actual_types)
        self.assertEqual(actual_types["Technology2030"], "string")
