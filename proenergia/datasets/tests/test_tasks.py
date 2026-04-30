import shutil
from os.path import join
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import patch

import geopandas as gpd
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from proenergia.datasets.models import (
    DataModel,
    Scenario,
    ScenarioData,
    ScenarioFile,
    VectorDataset,
    VectorFile,
)
from proenergia.datasets.tasks import (
    import_scenario_data_csv,
    merge_vector_scenario_files,
    to_pmtiles,
)


class TestToPmtiles(TestCase):
    def setUp(self):
        airports = "./proenergia/datasets/fixtures/airports_OSM.gpkg"
        schools = "./proenergia/datasets/fixtures/schools.zip"
        temp_dir = mkdtemp()
        self.temp_airports = join(temp_dir, "airports_OSM.gpkg")
        self.temp_schools = join(temp_dir, "schools.zip")
        shutil.copy(airports, self.temp_airports)
        shutil.copy(schools, self.temp_schools)

    def test_to_pmtiles(self):
        to_pmtiles(self.temp_airports)
        to_pmtiles(self.temp_schools)
        assert Path(self.temp_airports).exists()
        assert Path(self.temp_schools).exists()


class TestGeneratePmtiles(APITestCase):
    def setUp(self):
        self.airports = "./proenergia/datasets/fixtures/airports_OSM.gpkg"
        self.client = Client()
        # Create superuser for admin access
        self.superadmin = get_user_model().objects.create_superuser(
            username="superadmin", email="admin@example.com", password="testpass123"
        )
        self.dataset = VectorDataset.objects.create(
            name="Airports",
            description="Administratives Boundaries",
            source="OSM",
            is_public=True,
            is_approved=True,
            created_by=self.superadmin,
            last_updated_by=self.superadmin,
        )

    @patch("proenergia.datasets.tasks.generate_pmtiles.delay")
    def test_generate_pm_tiles(self, mock_generate_pmtiles):
        self.client.login(username="superadmin", password="testpass123")
        url = reverse("admin:datasets_vectorfile_add")
        with open(self.airports, "rb") as file_data:
            self.client.post(
                url,
                {"file": file_data, "dataset": self.dataset.id},
                follow=True,
            )
        self.assertEqual(VectorFile.objects.count(), 1)
        vf = VectorFile.objects.first()
        self.assertEqual(vf.status, "created")

        mock_generate_pmtiles.assert_called_once_with(vf.id)


class TestScenarioFilePostSaveTasks(TestCase):
    def setUp(self):
        self.scenario_csv = "./proenergia/datasets/fixtures/scenario.csv"
        self.scenario_csv_2 = "./proenergia/datasets/fixtures/scenario_2.csv"

    def test_merge_vector_scenario_files(self):
        vector = "./proenergia/datasets/fixtures/sample.fgb"
        scenario_fgb = join(mkdtemp(), "scenario.fgb")
        merge_vector_scenario_files(
            vector,
            self.scenario_csv,
            ["cost", "location"],
            scenario_fgb,
        )
        merged_gdf = gpd.read_file(scenario_fgb)

        # Verify that cost and location columns are present, but country is not
        self.assertTrue("id" in merged_gdf.columns)
        self.assertTrue("area" in merged_gdf.columns)
        self.assertTrue("cost" in merged_gdf.columns)
        self.assertTrue("location" in merged_gdf.columns)
        self.assertFalse("country" in merged_gdf.columns)

    @patch("proenergia.datasets.tasks.generate_pmtiles.delay")
    @patch("proenergia.datasets.tasks.generate_scenario_pmtiles.delay")
    def test_generate_scenario_pmtiles(
        self, mock_generate_scenario_pmtiles, mock_generate_pmtiles
    ):
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
        mock_generate_pmtiles.assert_called_with(self.vector_file_1.id)
        mock_generate_scenario_pmtiles.assert_called_with(self.scenario_file_1.id)

        # import csv and check ScenarioData items were created
        import_scenario_data_csv(self.scenario_file_1.id)
        self.assertEqual(
            ScenarioData.objects.filter(scenario=self.scenario_1).count(), 11
        )
        self.assertEqual(
            ScenarioData.objects.filter(
                scenario=self.scenario_1, metadata__location="Tete"
            ).count(),
            3,
        )

        # Create a new ScenarioFile and check if the data was updated
        with open(self.scenario_csv_2, "rb") as f:
            file_content = f.read()

        scenario_file = SimpleUploadedFile(
            "scenario.csv", file_content, content_type="text/csv"
        )
        self.scenario_file_2 = ScenarioFile.objects.create(
            scenario=self.scenario_1,
            file=scenario_file,
            created_by=self.superadmin,
            status="ready",
        )

        mock_generate_pmtiles.assert_called_with(self.vector_file_1.id)
        mock_generate_scenario_pmtiles.assert_called_with(self.scenario_file_2.id)

        import_scenario_data_csv(self.scenario_file_2.id)
        self.assertEqual(
            ScenarioData.objects.filter(scenario=self.scenario_1).count(), 12
        )
        self.assertEqual(
            ScenarioData.objects.filter(
                scenario=self.scenario_1, metadata__cost=777
            ).count(),
            1,
        )
        self.assertEqual(
            ScenarioData.objects.filter(
                scenario=self.scenario_1, metadata__cost=1111
            ).count(),
            1,
        )
        self.assertEqual(
            ScenarioData.objects.filter(
                scenario=self.scenario_1, metadata__location="Tete"
            ).count(),
            4,
        )
        # Chifunde entry should be deleted as its not present in the new file
        self.assertEqual(
            ScenarioData.objects.filter(
                scenario=self.scenario_1, metadata__location="Chifunde"
            ).count(),
            0,
        )


class TestImportScenarioDataCsvCacheInvalidation(TestCase):
    """Verify that cache invalidation is triggered after a successful CSV import."""

    def setUp(self):
        self.scenario_csv = "./proenergia/datasets/fixtures/scenario.csv"
        superadmin = get_user_model().objects.create_superuser(
            username="superadmin", email="admin@example.com", password="testpass123"
        )
        dataset = VectorDataset.objects.create(
            name="Boundaries",
            description="Administrative Boundaries",
            source="OSM",
            is_public=True,
            is_approved=True,
            created_by=superadmin,
            last_updated_by=superadmin,
        )
        file = SimpleUploadedFile(
            "v.geojson", b"file_content", content_type="application/json"
        )
        VectorFile.objects.create(
            dataset=dataset,
            file=file,
            created_by=superadmin,
            status="ready",
        )
        model = DataModel.objects.create(
            name="Test Model",
            filter_fields=[{"label": "Location", "column": "location"}],
            popup_fields=[{"label": "Location", "column": "location"}],
        )
        self.scenario = Scenario.objects.create(
            name="Test Scenario",
            vector_dataset=dataset,
            model=model,
        )
        self.superadmin = superadmin

    @patch("proenergia.datasets.tasks.generate_pmtiles.delay")
    @patch("proenergia.datasets.tasks.generate_scenario_pmtiles.delay")
    @patch("proenergia.datasets.tasks.invalidate_scenario_summary_cache")
    def test_cache_invalidated_after_successful_import(
        self, mock_invalidate, mock_scenario_pmtiles, mock_pmtiles
    ):
        with open(self.scenario_csv, "rb") as f:
            content = f.read()
        scenario_file = ScenarioFile.objects.create(
            scenario=self.scenario,
            file=SimpleUploadedFile("scenario.csv", content, content_type="text/csv"),
            created_by=self.superadmin,
            status="ready",
        )

        import_scenario_data_csv(scenario_file.id)

        mock_invalidate.assert_called_once_with(self.scenario.id)
