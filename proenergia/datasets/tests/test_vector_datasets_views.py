from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import VectorDataset, VectorFile


class TestVectorDatasetListDetailViews(APITestCase):
    def setUp(self):
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
            name="Boundaries",
            description="Administratives Boundaries",
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
        )
        file = SimpleUploadedFile(
            "new.geojson", b"file_content", content_type="application/json"
        )
        self.vector_file_2 = VectorFile.objects.create(
            dataset=self.dataset_1,
            file=file,
            created_by=self.superadmin_user,
        )
        self.url = reverse("datasets:vector-list")

    def test_vector_datasets_list_unauthenticated(self):
        req = self.client.get(self.url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 1
        assert req.data.get("results")[0]["name"] == "Boundaries"
        assert req.data.get("results")[0]["description"] == "Administratives Boundaries"

    def test_vector_datasets_list_admin_user(self):
        self.client.force_authenticate(user=self.admin_user)
        req = self.client.get(self.url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 1
        assert req.data.get("results")[0]["name"] == "Boundaries"
        assert req.data.get("results")[0]["description"] == "Administratives Boundaries"
        assert req.data.get("results")[0]["raw_file"] == self.vector_file_2.file.name

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
        assert req.data.get("name") == "Boundaries"
        assert req.data.get("description") == "Administratives Boundaries"
        assert req.data.get("created")
        assert req.data.get("updated")
        assert req.data.get("source") == "OSM"
        assert req.data.get("raw_file") == self.vector_file_2.file.name

        url = reverse("datasets:vector-detail", args=[self.dataset_2.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_403_FORBIDDEN

    def test_vector_datasets_detail_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("datasets:vector-detail", args=[self.dataset_1.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("name") == "Boundaries"
        # only superadmin can access private/non-approved dataset
        url = reverse("datasets:vector-detail", args=[self.dataset_2.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_403_FORBIDDEN

    def test_vector_datasets_detail_superadmin(self):
        file = SimpleUploadedFile(
            "new.kml", b"file_content", content_type="application/json"
        )
        VectorFile.objects.create(
            dataset=self.dataset_2,
            file=file,
            created_by=self.superadmin_user,
        )
        self.client.force_authenticate(user=self.superadmin_user)

        url = reverse("datasets:vector-detail", args=[self.dataset_2.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("name") == "Roads"
        assert req.data.get("raw_file") == "vector/new.kml"

        url = reverse("datasets:vector-detail", args=[self.dataset_3.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("name") == "Buildings"
        assert req.data.get("raw_file") is None

    def tearDown(self):
        VectorFile.objects.all().delete()
