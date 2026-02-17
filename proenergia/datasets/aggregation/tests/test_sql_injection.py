"""
SQL injection security tests for the aggregation module.

These tests verify that user input is properly sanitized and parameterized
to prevent SQL injection attacks.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model

from proenergia.datasets.models import (
    DataModel,
    Scenario,
    ScenarioDataMetrics,
    VectorDataset,
)
from proenergia.datasets.aggregation import FilterParser, SummaryQueryBuilder

User = get_user_model()


class SQLInjectionSecurityTest(TestCase):
    """Test that the aggregation module is safe from SQL injection attacks."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="sqlinject_testuser", password="testpass"
        )

        # Create a vector dataset (required for Scenario)
        self.vector_dataset = VectorDataset.objects.create(
            name="Test Vector Dataset",
            created_by=self.user,
            last_updated_by=self.user,
        )

        # Create a data model with field types
        self.model = DataModel.objects.create(
            name="SQL Injection Test Model",
            metric_field_types={
                "Pop2030": "numeric",
                "district": "string",
                "Technology2030": "string",
                "location": "string",
                "InvestmentGen": "numeric",
            },
        )

        # Create a scenario
        self.scenario = Scenario.objects.create(
            name="SQL Injection Test Scenario",
            model=self.model,
            vector_dataset=self.vector_dataset,
        )

        # Add some test metrics
        metrics_data = [
            (1, "Pop2030", 1000.0, None),
            (1, "district", None, "Central"),
            (1, "Technology2030", None, "SHS"),
            (1, "location", None, "Maputo"),
            (1, "InvestmentGen", 500.0, None),
        ]

        for feature_id, key, numeric_value, string_value in metrics_data:
            ScenarioDataMetrics.objects.create(
                scenario=self.scenario,
                feature_id=feature_id,
                key=key,
                numeric_value=numeric_value,
                string_value=string_value,
            )

    def test_sql_injection_in_filter_values(self):
        """Test that malicious SQL in filter values is properly escaped."""
        parser = FilterParser(self.model.metric_field_types)
        query_builder = SummaryQueryBuilder()

        # Attempt SQL injection via filter value
        malicious_values = [
            "Maputo'; DROP TABLE datasets_scenariodatametrics; --",
            "1 OR 1=1",
            "'; DELETE FROM users WHERE '1'='1",
            '" OR ""="',
        ]

        for malicious_value in malicious_values:
            # This should not raise an error - the value should be safely parameterized
            filter_string = f"location={malicious_value}"
            filters = parser.parse_filter_string(filter_string)

            # Build SQL with malicious value
            filter_sql, filter_params, _ = parser.build_filter_sql(filters)

            # The malicious value should be in params, not in SQL string
            self.assertIn(malicious_value, filter_params)
            # SQL string should only contain placeholders
            self.assertIn("%s", filter_sql)
            # Malicious SQL should not be in the SQL string itself
            self.assertNotIn("DROP TABLE", filter_sql)
            self.assertNotIn("DELETE FROM", filter_sql)

    def test_field_name_validation(self):
        """Test that only whitelisted field names are accepted."""
        parser = FilterParser(self.model.metric_field_types)

        # These field names should be rejected
        malicious_field_names = [
            "district; DROP TABLE test;--",
            "district' OR '1'='1",
            "district); DELETE FROM users; --",
            "nonexistent_field",
            "1=1",
        ]

        for field_name in malicious_field_names:
            filter_string = f"{field_name}=value"

            # Should raise ValueError for non-whitelisted fields
            with self.assertRaises(ValueError) as cm:
                parser.parse_filter_string(filter_string)

            self.assertIn("not configured", str(cm.exception))

    def test_operator_validation(self):
        """Test that only valid operators are accepted for each field type."""
        parser = FilterParser(self.model.metric_field_types)

        # Test invalid operators for numeric fields
        invalid_numeric_ops = ["in", "like", "or", "drop"]
        for op in invalid_numeric_ops:
            filter_string = f"Pop2030__{op}=1000"
            with self.assertRaises(ValueError) as cm:
                parser.parse_filter_string(filter_string)
            self.assertIn("operator", str(cm.exception).lower())

        # Test invalid operators for string fields
        invalid_string_ops = ["gte", "lte", "gt", "lt"]
        for op in invalid_string_ops:
            filter_string = f"district__{op}=Central"
            with self.assertRaises(ValueError) as cm:
                parser.parse_filter_string(filter_string)
            # Check that error mentions unsupported operator
            error_msg = str(cm.exception).lower()
            self.assertTrue(
                "unsupported" in error_msg or "not valid" in error_msg,
                f"Expected 'unsupported' or 'not valid' in error message, got: {cm.exception}",
            )

    def test_sql_special_characters_in_values(self):
        """Test that SQL special characters in values are properly handled."""
        parser = FilterParser(self.model.metric_field_types)

        # Values with SQL special characters
        special_values = [
            "O'Reilly",  # Single quote
            'Name with "quotes"',  # Double quotes
            "50% discount",  # Percent sign
            "user@example.com",  # At sign
            "path/to/file",  # Slashes
            "value;with;semicolons",  # Semicolons
        ]

        for value in special_values:
            filter_string = f"location={value}"

            # Should not raise an error
            filters = parser.parse_filter_string(filter_string)
            filter_sql, filter_params, _ = parser.build_filter_sql(filters)

            # Value should be in parameters, properly escaped
            self.assertIn(value, filter_params)
            # SQL should use placeholders
            self.assertIn("%s", filter_sql)

    def test_query_execution_with_malicious_input(self):
        """Test that queries execute safely with malicious input."""
        parser = FilterParser(self.model.metric_field_types)
        query_builder = SummaryQueryBuilder()

        # Build query with malicious filter value
        malicious_filter = "location=Maputo' OR '1'='1"
        filters = parser.parse_filter_string(malicious_filter)
        filter_sql, filter_params, _ = parser.build_filter_sql(filters)

        # Fill in scenario IDs
        filter_params = parser.fill_scenario_ids(filter_params, self.scenario.id)

        # Build and execute query - should not cause SQL injection
        sql, params = query_builder.build_filtered_query(
            self.scenario.id, "Pop2030", "numeric", filter_sql, filter_params
        )

        # Execute query - should work safely
        results = query_builder.execute_query(sql, params)

        # Should return empty results (no match for malicious value)
        # Not an error, just no matching data
        self.assertIsNotNone(results)
        if results:
            # If there are results, count should be 0 since the value doesn't match
            self.assertEqual(results[0].get("count", 0), 0)

    def test_multiple_group_by_field_limit(self):
        """Test that group_by is limited to prevent complex nested queries."""
        # This is enforced at the view level, but let's verify the query builder
        # doesn't accept more than 2 group fields
        query_builder = SummaryQueryBuilder()

        # Should raise error for more than 2 group fields
        with self.assertRaises(ValueError) as cm:
            query_builder.build_multi_group_query(
                self.scenario.id,
                "Pop2030",
                "numeric",
                ["field1", "field2", "field3"],  # Too many fields
                "",
                [],
            )

        self.assertIn("Maximum of 2", str(cm.exception))

    def test_alias_generation_safety(self):
        """Test that SQL aliases are safely generated, not from user input."""
        parser = FilterParser(self.model.metric_field_types)

        # Multiple filters should generate f0, f1, f2 etc. aliases
        filter_string = "location=Maputo,Pop2030__gte=1000,district=Central"
        filters = parser.parse_filter_string(filter_string)
        filter_sql, _, _ = parser.build_filter_sql(filters)

        # Check that aliases are present and follow expected pattern
        self.assertIn("f0", filter_sql)
        self.assertIn("f1", filter_sql)
        self.assertIn("f2", filter_sql)

        # Aliases should be hardcoded in SQL, not from parameters
        self.assertIn("INNER JOIN datasets_scenariodatametrics f0", filter_sql)
        self.assertIn("INNER JOIN datasets_scenariodatametrics f1", filter_sql)
        self.assertIn("INNER JOIN datasets_scenariodatametrics f2", filter_sql)
