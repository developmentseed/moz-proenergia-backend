import shutil
from os.path import join
from pathlib import Path
from tempfile import mkdtemp

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from proenergia.datasets.models import VectorDataset, VectorFile
from proenergia.datasets.tasks import generate_pmtiles, to_pmtiles


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
            name="Boundaries",
            description="Administratives Boundaries",
            source="OSM",
            is_public=True,
            is_approved=True,
            created_by=self.superadmin,
            last_updated_by=self.superadmin,
        )

    def test_generate_pm_tiles(self):
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
        # execute function
        result = generate_pmtiles.apply([vf])
        self.assertTrue(result.successful())
        self.assertEqual(vf.status, "ready")
