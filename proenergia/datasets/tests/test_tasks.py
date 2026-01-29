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
    ScenarioFile,
    VectorDataset,
    VectorFile,
)
from proenergia.datasets.tasks import merge_vector_scenario_files, to_pmtiles


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


class TestMergeVectorScenarioFiles(TestCase):
    def test_merge_vector_scenario_files(self):
        vector = "./proenergia/datasets/fixtures/sample.fgb"
        scenario = "./proenergia/datasets/fixtures/scenario.csv"
        scenario_fgb = join(mkdtemp(), "scenario.fgb")
        filter_fields = [
            {
                "label": "Cost",
                "description": "Cost to eletrify",
                "column": "cost",
            },
            {
                "label": "Location",
                "description": "Location of the entity",
                "column": "location",
            },
        ]
        merge_vector_scenario_files(vector, scenario, filter_fields, scenario_fgb)
        merged_gdf = gpd.read_file(scenario_fgb)

        # Verify that cost and location columns are present, but country is not
        self.assertTrue("id" in merged_gdf.columns)
        self.assertTrue("area" in merged_gdf.columns)
        self.assertTrue("cost" in merged_gdf.columns)
        self.assertTrue("location" in merged_gdf.columns)
        self.assertFalse("country" in merged_gdf.columns)

    @patch("proenergia.datasets.tasks.generate_pmtiles.delay")
    @patch("proenergia.datasets.tasks.generate_scenario_pmtiles.delay")
    def test_generate_scenario_pmtiles(self, mock_scenario, mock_2):
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
        file = SimpleUploadedFile(
            "old.csv", b"id,col_b\n1,blah", content_type="text/csv"
        )
        self.scenario_file_1 = ScenarioFile.objects.create(
            scenario=self.scenario_1,
            file=file,
            created_by=self.superadmin,
            status="ready",
        )
        mock_scenario.assert_called_with(self.scenario_file_1.id)
