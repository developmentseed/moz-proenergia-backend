from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import DataModel, Scenario, VectorDataset, VectorFile


class TestVectorDatasetListDetailViews(APITestCase):
    @patch("proenergia.datasets.models.generate_pmtiles.delay")
    def setUp(self, mock_generate_pmtiles):
        self.superadmin_user = get_user_model().objects.create_superuser(
            username="superadmin",
            email="superadmin@example.com",
            password="testpass123",
        )
        self.admin_user = get_user_model().objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            is_staff=True,
        )
        self.dataset_1 = VectorDataset.objects.create(
            name="Administrative Boundaries",
            description="Administrative Boundaries",
            source="OSM",
            is_public=True,
            is_approved=True,
            created_by=self.superadmin_user,
            last_updated_by=self.superadmin_user,
        )
        self.dataset_2 = VectorDataset.objects.create(
            name="Roads",
            is_public=False,
            is_approved=True,
            created_by=self.superadmin_user,
            last_updated_by=self.superadmin_user,
        )
        self.dataset_3 = VectorDataset.objects.create(
            name="Buildings",
            is_public=True,
            is_approved=False,
            created_by=self.superadmin_user,
            last_updated_by=self.superadmin_user,
        )
        file = SimpleUploadedFile(
            "old.geojson", b"file_content", content_type="application/json"
        )
        self.vector_file_1 = VectorFile.objects.create(
            dataset=self.dataset_1,
            file=file,
            created_by=self.superadmin_user,
            status="ready",
        )
        file = SimpleUploadedFile(
            "new.geojson", b"file_content", content_type="application/json"
        )
        self.vector_file_2 = VectorFile.objects.create(
            dataset=self.dataset_1,
            file=file,
            created_by=self.superadmin_user,
            status="ready",
        )
        self.url = reverse("datasets:vector-list")

    def test_vector_datasets_list_unauthenticated(self):
        req = self.client.get(self.url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 1
        assert req.data.get("results")[0]["name"] == "Administrative Boundaries"
        assert req.data.get("results")[0]["description"] == "Administrative Boundaries"

    def test_vector_datasets_list_admin_user(self):
        self.client.force_authenticate(user=self.admin_user)
        req = self.client.get(self.url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 1
        assert req.data.get("results")[0]["name"] == "Administrative Boundaries"
        assert req.data.get("results")[0]["description"] == "Administrative Boundaries"
        assert (
            req.data.get("results")[0]["raw_file"]
            == "vector/administrative-boundaries_v2.geojson"
        )

    def test_vector_datasets_list_superadmin_user(self):
        self.client.force_authenticate(user=self.superadmin_user)
        req = self.client.get(self.url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 3

    def test_vector_datasets_list_filter(self):
        req = self.client.get(self.url, {"name": "Bound"})
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 1

        req = self.client.get(self.url, {"name": "Test"})
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 0

    def test_vector_datasets_detail_unauthenticated(self):
        url = reverse("datasets:vector-detail", args=[self.dataset_1.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("name") == "Administrative Boundaries"
        assert req.data.get("description") == "Administrative Boundaries"
        assert req.data.get("created")
        assert req.data.get("updated")
        assert req.data.get("source") == "OSM"
        assert req.data.get("raw_file") == "vector/administrative-boundaries_v2.geojson"

        url = reverse("datasets:vector-detail", args=[self.dataset_2.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_403_FORBIDDEN

    def test_vector_datasets_detail_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("datasets:vector-detail", args=[self.dataset_1.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("name") == "Administrative Boundaries"
        # only superadmin can access private/non-approved dataset
        url = reverse("datasets:vector-detail", args=[self.dataset_2.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_403_FORBIDDEN

    @patch("proenergia.datasets.models.generate_pmtiles.delay")
    def test_vector_datasets_detail_superadmin(self, mock_generate_pmtiles):
        file = SimpleUploadedFile(
            "new.kml", b"file_content", content_type="application/json"
        )
        VectorFile.objects.create(
            dataset=self.dataset_2,
            file=file,
            created_by=self.superadmin_user,
            status="ready",
        )
        self.client.force_authenticate(user=self.superadmin_user)

        url = reverse("datasets:vector-detail", args=[self.dataset_2.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("name") == "Roads"
        assert req.data.get("raw_file") == "vector/roads_v1.kml"

        url = reverse("datasets:vector-detail", args=[self.dataset_3.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("name") == "Buildings"
        assert req.data.get("raw_file") is None

    def test_filters(self):
        # create another public & approved vector dataset
        self.dataset_4 = VectorDataset.objects.create(
            name="Cycleways",
            is_public=True,
            is_approved=True,
            created_by=self.superadmin_user,
            last_updated_by=self.superadmin_user,
        )
        model_1 = DataModel.objects.create(
            name="PUE",
            filter_fields=[],
            popup_fields=[],
            summary_fields=[],
            visualization_column="Pop",
            color_coding=[],
        )
        model_1.contextual_layers.add(self.dataset_4)

        req = self.client.get(self.url, {"model": model_1.id})
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 1
        assert req.data.get("results")[0]["name"] == "Cycleways"

        self.scenario_1 = Scenario.objects.create(
            name="Least Cost Electrification",
            vector_dataset=self.dataset_1,
            model=model_1,
        )
        # after creating the scenario, it should return 2 items
        req = self.client.get(self.url, {"model": model_1.id})
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 2
        assert req.data.get("results")[0]["name"] == "Administrative Boundaries"
        assert req.data.get("results")[1]["name"] == "Cycleways"

        model_2 = DataModel.objects.create(
            name="New model",
            filter_fields=[],
            popup_fields=[],
            summary_fields=[],
            visualization_column="Pop",
            color_coding=[],
        )
        # no vector datasets assigned to model_2, so it should not return results
        req = self.client.get(self.url, {"model": model_2.id})
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 0

    def tearDown(self):
        VectorFile.objects.all().delete()
