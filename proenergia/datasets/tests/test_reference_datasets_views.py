from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from ..models import DataModel, ReferenceDataset, ReferenceFile


class TestReferenceDatasetListDetailViews(APITestCase):
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
        self.dataset_1 = ReferenceDataset.objects.create(
            name="Administrative Boundaries",
            description="Administrative Boundaries",
            source="OSM",
            is_public=True,
            is_approved=True,
            created_by=self.superadmin_user,
            last_updated_by=self.superadmin_user,
        )
        self.dataset_2 = ReferenceDataset.objects.create(
            name="Roads",
            is_public=False,
            is_approved=True,
            created_by=self.superadmin_user,
            last_updated_by=self.superadmin_user,
        )
        self.dataset_3 = ReferenceDataset.objects.create(
            name="Buildings",
            is_public=True,
            is_approved=False,
            created_by=self.superadmin_user,
            last_updated_by=self.superadmin_user,
        )
        file = SimpleUploadedFile(
            "old.geotiff", b"file_content", content_type="image/tiff"
        )
        self.reference_file_1 = ReferenceFile.objects.create(
            dataset=self.dataset_1,
            file=file,
            created_by=self.superadmin_user,
        )
        file = SimpleUploadedFile(
            "new.pdf", b"file_content", content_type="application/pdf"
        )
        self.reference_file_2 = ReferenceFile.objects.create(
            dataset=self.dataset_1,
            file=file,
            created_by=self.superadmin_user,
        )
        self.url = reverse("datasets:reference-list")

    def test_reference_datasets_list_unauthenticated(self):
        req = self.client.get(self.url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 1
        assert req.data.get("results")[0]["name"] == "Administrative Boundaries"
        assert req.data.get("results")[0]["description"] == "Administrative Boundaries"

    def test_reference_datasets_list_admin_user(self):
        self.client.force_authenticate(user=self.admin_user)
        req = self.client.get(self.url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 2
        assert req.data.get("results")[0]["name"] == "Administrative Boundaries"
        assert req.data.get("results")[0]["description"] == "Administrative Boundaries"
        assert (
            req.data.get("results")[0]["raw_file"]
            == "reference/administrative-boundaries_v2.pdf"
        )
        assert req.data.get("results")[1]["name"] == "Roads"

    def test_reference_datasets_list_superadmin_user(self):
        self.client.force_authenticate(user=self.superadmin_user)
        req = self.client.get(self.url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 3

    def test_reference_datasets_list_filter(self):
        req = self.client.get(self.url, {"name": "Bound"})
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 1

        req = self.client.get(self.url, {"name": "Test"})
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 0

    def test_reference_datasets_detail_unauthenticated(self):
        url = reverse("datasets:reference-detail", args=[self.dataset_1.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("name") == "Administrative Boundaries"
        assert req.data.get("description") == "Administrative Boundaries"
        assert req.data.get("created")
        assert req.data.get("updated")
        assert req.data.get("source") == "OSM"
        assert req.data.get("raw_file") == "reference/administrative-boundaries_v2.pdf"

        url = reverse("datasets:reference-detail", args=[self.dataset_2.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_403_FORBIDDEN

    def test_reference_datasets_detail_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        # can access public dataset
        url = reverse("datasets:reference-detail", args=[self.dataset_1.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("name") == "Administrative Boundaries"
        # admin users can access private and approved dataset
        url = reverse("datasets:reference-detail", args=[self.dataset_2.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("name") == "Roads"
        # only superadmin can access private non-approved datasets
        url = reverse("datasets:reference-detail", args=[self.dataset_3.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_403_FORBIDDEN

    def test_reference_datasets_detail_superadmin(self):
        file = SimpleUploadedFile("new.csv", b"file_content", content_type="text/csv")
        ReferenceFile.objects.create(
            dataset=self.dataset_2,
            file=file,
            created_by=self.superadmin_user,
        )
        self.client.force_authenticate(user=self.superadmin_user)

        url = reverse("datasets:reference-detail", args=[self.dataset_2.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("name") == "Roads"
        assert req.data.get("raw_file") == "reference/roads_v1.csv"

        url = reverse("datasets:reference-detail", args=[self.dataset_3.id])
        req = self.client.get(url)
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("name") == "Buildings"
        assert req.data.get("raw_file") is None

    def test_filters(self):
        # create another public & approved reference dataset
        self.dataset_4 = ReferenceDataset.objects.create(
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
        model_1.reference_datasets.add(self.dataset_4)

        req = self.client.get(self.url, {"model": model_1.id})
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 1
        assert req.data.get("results")[0]["name"] == "Cycleways"

        model_2 = DataModel.objects.create(
            name="New model",
            filter_fields=[],
            popup_fields=[],
            summary_fields=[],
            visualization_column="Pop",
            color_coding=[],
        )
        # no reference datasets assigned to model_2, so it should not return results
        req = self.client.get(self.url, {"model": model_2.id})
        assert req.status_code == status.HTTP_200_OK
        assert req.data.get("count") == 0

    def tearDown(self):
        ReferenceFile.objects.all().delete()
