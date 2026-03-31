from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from proenergia.datasets.models import RasterDataset, RasterFile


class RasterDatasetAdmin(TestCase):
    def setUp(self):
        self.client = Client()
        # Create superuser for admin access
        self.superadmin = get_user_model().objects.create_superuser(
            username="superadmin", email="admin@example.com", password="testpass123"
        )

        # Create admin user
        self.admin_user = get_user_model().objects.create_user(
            username="admin_user",
            email="admin_user_2@example.com",
            password="testpass123",
            is_staff=True,
        )

    def test_creation_superuser(self):
        self.client.login(username="superadmin", password="testpass123")
        url = reverse("admin:datasets_rasterdataset_add")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Superadmins can toggle public/approved fields
        self.assertContains(response, "Is public")
        self.assertContains(response, "Is approved")

        data = {
            "name_en": "Test Dataset",
            "description_en": "Test Description",
        }
        response = self.client.post(url, data)

        # Should redirect to changelist after successful creation
        self.assertEqual(response.status_code, 302)

        # Verify that it was created with the correct user
        dataset = RasterDataset.objects.get(name="Test Dataset")
        self.assertEqual(dataset.created_by, self.superadmin)
        self.assertEqual(dataset.last_updated_by, self.superadmin)

    def test_creation_admin(self):
        self.client.login(username="admin_user", password="testpass123")
        url = reverse("admin:datasets_rasterdataset_add")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # should not include public/approved toggles
        self.assertNotContains(response, "Is public")
        self.assertNotContains(response, "Is approved")

        data = {
            "name_en": "Test Dataset",
            "description_en": "Test Description",
        }
        response = self.client.post(url, data)

        # Should redirect to changelist after successful creation
        self.assertEqual(response.status_code, 302)

        # Verify that it was created with the correct user
        dataset = RasterDataset.objects.get(name="Test Dataset")
        self.assertEqual(dataset.created_by, self.admin_user)
        self.assertEqual(dataset.last_updated_by, self.admin_user)

    def test_admin_forbidden_update(self):
        dataset = RasterDataset.objects.create(
            name="Test Dataset",
            description="Test Description",
            created_by=self.superadmin,
            last_updated_by=self.superadmin,
        )
        self.client.login(username="admin_user", password="testpass123")
        url = reverse("admin:datasets_rasterdataset_change", args=[dataset.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        data = {
            "name": "Test Dataset",
            "description": "Updated Description",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)

        # Confirm update was not successful
        dataset.refresh_from_db()
        self.assertEqual(dataset.name, "Test Dataset")
        self.assertEqual(dataset.description, "Test Description")
        self.assertEqual(dataset.created_by, self.superadmin)
        self.assertEqual(dataset.last_updated_by, self.superadmin)

    def test_admin_successful_update(self):
        dataset = RasterDataset.objects.create(
            name="Test Dataset",
            description="Test Description",
            created_by=self.admin_user,
            last_updated_by=self.superadmin,
        )
        self.client.login(username="admin_user", password="testpass123")
        url = reverse("admin:datasets_rasterdataset_change", args=[dataset.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = {
            "name_en": "Updated Dataset",
            "description_en": "Updated Description",
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)

        # Confirm that the update was successful
        dataset.refresh_from_db()
        self.assertEqual(dataset.name, "Updated Dataset")
        self.assertEqual(dataset.description, "Updated Description")
        self.assertEqual(dataset.created_by, self.admin_user)
        self.assertEqual(dataset.last_updated_by, self.admin_user)

    def test_superadmin_successful_update(self):
        dataset = RasterDataset.objects.create(
            name="Test Dataset",
            description="Test Description",
            created_by=self.admin_user,
            last_updated_by=self.admin_user,
        )
        self.client.login(username="superadmin", password="testpass123")
        url = reverse("admin:datasets_rasterdataset_change", args=[dataset.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = {
            "name_en": "Updated Dataset",
            "description_en": "Updated Description",
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, 302)

        # Confirm that the update was successful
        dataset.refresh_from_db()
        self.assertEqual(dataset.name, "Updated Dataset")
        self.assertEqual(dataset.description, "Updated Description")
        self.assertEqual(dataset.created_by, self.admin_user)
        self.assertEqual(dataset.last_updated_by, self.superadmin)

    def test_superadmin_actions(self):
        dataset = RasterDataset.objects.create(
            name="Test Dataset",
            description="Test Description",
            created_by=self.admin_user,
            last_updated_by=self.admin_user,
            is_public=False,
            is_approved=False,
        )
        self.client.login(username="superadmin", password="testpass123")
        url = reverse("admin:datasets_rasterdataset_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Make dataset public")
        self.assertContains(response, "Make dataset private")
        self.assertContains(response, "Approve dataset")
        self.assertContains(response, "Set as not approved")

        # make dataset public
        response = self.client.post(
            url,
            {
                "action": "make_public",
                "_selected_action": str(dataset.id),
                "post": "yes",
            },
            follow=True,
        )
        dataset.refresh_from_db()
        self.assertContains(response, f"Set {dataset.name} as public")
        self.assertTrue(dataset.is_public)

        # approve dataset
        response = self.client.post(
            url,
            {
                "action": "approve",
                "_selected_action": str(dataset.id),
                "post": "yes",
            },
            follow=True,
        )
        dataset.refresh_from_db()
        self.assertContains(response, f"Set {dataset.name} as approved")
        self.assertTrue(dataset.is_approved)

        # make dataset private
        response = self.client.post(
            url,
            {
                "action": "make_private",
                "_selected_action": str(dataset.id),
                "post": "yes",
            },
            follow=True,
        )
        dataset.refresh_from_db()
        self.assertContains(response, f"Set {dataset.name} as private")
        self.assertFalse(dataset.is_public)

        # disapprove dataset
        response = self.client.post(
            url,
            {
                "action": "disapprove",
                "_selected_action": str(dataset.id),
                "post": "yes",
            },
            follow=True,
        )
        dataset.refresh_from_db()
        self.assertContains(response, f"Set {dataset.name} as not approved")
        self.assertFalse(dataset.is_approved)

    def test_admin_actions(self):
        dataset = RasterDataset.objects.create(
            name="Test Dataset",
            description="Test Description",
            created_by=self.admin_user,
            last_updated_by=self.admin_user,
            is_public=False,
            is_approved=False,
        )
        self.client.login(username="admin_user", password="testpass123")
        url = reverse("admin:datasets_rasterdataset_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Make dataset public")
        self.assertNotContains(response, "Make dataset private")
        self.assertNotContains(response, "Approve dataset")
        self.assertNotContains(response, "Set as not approved")

        # confirm that posting actions don't change the public and approved statuses
        response = self.client.post(
            url,
            {
                "action": "make_public",
                "_selected_action": str(dataset.id),
                "post": "yes",
            },
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            url,
            {
                "action": "approve",
                "_selected_action": str(dataset.id),
                "post": "yes",
            },
        )
        self.assertEqual(response.status_code, 302)
        dataset.refresh_from_db()
        self.assertFalse(dataset.is_public)
        self.assertFalse(dataset.is_approved)


class RasterFileAdmin(TestCase):
    def setUp(self):
        self.client = Client()
        # Create superuser for admin access
        self.superadmin = get_user_model().objects.create_superuser(
            username="superadmin", email="admin@example.com", password="testpass123"
        )

        # Create admin user
        self.admin_user = get_user_model().objects.create_user(
            username="admin_user",
            email="admin_user_2@example.com",
            password="testpass123",
            is_staff=True,
        )
        self.dataset_1 = RasterDataset.objects.create(
            name="Boundaries",
            description="Administratives Boundaries",
            source="OSM",
            is_public=True,
            is_approved=True,
            created_by=self.superadmin,
            last_updated_by=self.superadmin,
        )
        self.dataset_2 = RasterDataset.objects.create(
            name="Coastline",
            source="OSM",
            is_public=True,
            is_approved=True,
            created_by=self.admin_user,
            last_updated_by=self.admin_user,
        )

    def test_raster_file_creation_superadmin(self):
        self.client.login(username="superadmin", password="testpass123")
        url = reverse("admin:datasets_rasterfile_add")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Dataset")
        self.assertContains(response, self.dataset_1.name)
        self.assertContains(response, self.dataset_2.name)
        self.assertContains(response, "File")
        self.assertNotContains(response, "Created")
        self.assertNotContains(response, "Created by")

        file = SimpleUploadedFile(
            "boundaries.geotiff", b"file_content", content_type="image/tiff"
        )

        data = {
            "dataset": str(self.dataset_1.id),
            "file": file,
        }
        response = self.client.post(url, data)

        self.assertEqual(RasterFile.objects.count(), 1)
        raster_file = RasterFile.objects.first()
        self.assertEqual(raster_file.created_by, self.superadmin)
        # Delete file
        RasterFile.objects.all().delete()

    def test_raster_file_creation_admin(self):
        self.client.login(username="admin_user", password="testpass123")
        url = reverse("admin:datasets_rasterfile_add")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Dataset")
        self.assertNotContains(response, self.dataset_1.name)
        self.assertContains(response, self.dataset_2.name)
        self.assertContains(response, "File")
        self.assertNotContains(response, "Created")
        self.assertNotContains(response, "Created by")

        file = SimpleUploadedFile(
            "boundaries.geotiff", b"file_content", content_type="image/tiff"
        )

        data = {
            "dataset": str(self.dataset_1.id),
            "file": file,
        }
        response = self.client.post(url, data)

        self.assertEqual(RasterFile.objects.count(), 0)

        # upload file to allowed dataset
        data = {
            "dataset": str(self.dataset_2.id),
            "file": SimpleUploadedFile(
                "boundaries.geotiff",
                b"file_content",
                content_type="image/tiff",
            ),
        }
        response = self.client.post(url, data)

        self.assertEqual(RasterFile.objects.count(), 1)
        raster_file = RasterFile.objects.first()
        self.assertEqual(raster_file.created_by, self.admin_user)
        # Delete file
        RasterFile.objects.all().delete()
