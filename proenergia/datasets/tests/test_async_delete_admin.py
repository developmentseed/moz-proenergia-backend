from unittest.mock import call, patch

from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from proenergia.datasets.models import (
    DataModel,
    Scenario,
    VectorDataset,
)


class AsyncDeleteAdminTestMixin:
    delete_task_path = "proenergia.datasets.admin.delete_item"

    def setUp(self):
        self.superadmin = get_user_model().objects.create_superuser(
            username="superadmin",
            email="superadmin@example.com",
            password="testpass123",
        )
        self.client.login(username="superadmin", password="testpass123")
        self.objects = self.create_objects()

    def _make_staff_user(self, *, with_delete_perm: bool):
        """
        Create a non-superuser staff account; optionally grant the global
        ``delete_<model>`` permission so the user appears in admin but does
        not necessarily have delete rights.
        """
        User = get_user_model()
        user = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            password="staffpass123",
            is_staff=True,
        )
        ct = ContentType.objects.get_for_model(self.model_class)
        # Always allow change/view so the user can reach the changelist.
        for codename_prefix in ("view", "change"):
            user.user_permissions.add(
                Permission.objects.get(
                    content_type=ct,
                    codename=f"{codename_prefix}_{ct.model}",
                )
            )
        if with_delete_perm:
            user.user_permissions.add(
                Permission.objects.get(
                    content_type=ct,
                    codename=f"delete_{ct.model}",
                )
            )
        return user

    def test_first_post_renders_confirmation_page_without_deleting(self):
        with patch(self.delete_task_path) as mock_delete:
            response = self.client.post(
                self.changelist_url,
                data={
                    "action": "async_delete",
                    ACTION_CHECKBOX_NAME: [str(o.pk) for o in self.objects],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "admin/datasets/async_delete_confirmation.html"
        )
        # No celery dispatch yet, no DB deletion
        mock_delete.delay.assert_not_called()
        for obj in self.objects:
            self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())

        # Confirmation page lists every selected object
        for obj in self.objects:
            self.assertContains(response, str(obj))

        # Hidden form fields needed for the second submit
        self.assertContains(response, 'name="post"')
        self.assertContains(response, 'value="async_delete"')

    def test_confirmed_post_enqueues_one_task_per_object(self):
        with patch(self.delete_task_path) as mock_delete:
            response = self.client.post(
                self.changelist_url,
                data={
                    "action": "async_delete",
                    ACTION_CHECKBOX_NAME: [str(o.pk) for o in self.objects],
                    "post": "yes",
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)

        expected_calls = [call(self.model_name, obj.id) for obj in self.objects]
        self.assertEqual(mock_delete.delay.call_count, len(self.objects))
        mock_delete.delay.assert_has_calls(expected_calls, any_order=True)

        # Action does not delete anything synchronously
        for obj in self.objects:
            self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())

        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(
            any("queued for deletion" in m for m in messages),
            f"Expected a 'queued for deletion' message, got: {messages}",
        )

    def test_confirmed_post_with_single_object(self):
        obj = self.objects[0]
        with patch(self.delete_task_path) as mock_delete:
            self.client.post(
                self.changelist_url,
                data={
                    "action": "async_delete",
                    ACTION_CHECKBOX_NAME: [str(obj.pk)],
                    "post": "yes",
                },
            )

        mock_delete.delay.assert_called_once_with(self.model_name, obj.id)

    def test_action_is_hidden_for_user_without_delete_permission(self):
        """
        ``@admin.action(permissions=["delete"])`` must hide the entry from
        the dropdown for users that don't have the global delete perm.
        """
        self._make_staff_user(with_delete_perm=False)
        self.client.logout()
        self.client.login(username="staff", password="staffpass123")

        response = self.client.get(self.changelist_url)
        self.assertEqual(response.status_code, 200)
        # The action's <option value="async_delete"> should not be rendered.
        self.assertNotContains(response, 'value="async_delete"')

    def test_post_without_delete_permission_is_rejected(self):
        """
        Even if a user crafts the POST manually, no celery task must be
        dispatched. Django either filters the action out (changelist
        re-renders with a "no action selected" warning) or PermissionDenied
        bubbles up as a 403; both are acceptable - the invariant is no
        dispatch.
        """
        self._make_staff_user(with_delete_perm=False)
        self.client.logout()
        self.client.login(username="staff", password="staffpass123")

        with patch(self.delete_task_path) as mock_delete:
            r1 = self.client.post(
                self.changelist_url,
                data={
                    "action": "async_delete",
                    ACTION_CHECKBOX_NAME: [str(o.pk) for o in self.objects],
                },
            )
            r2 = self.client.post(
                self.changelist_url,
                data={
                    "action": "async_delete",
                    ACTION_CHECKBOX_NAME: [str(o.pk) for o in self.objects],
                    "post": "yes",
                },
            )

        self.assertIn(r1.status_code, (200, 302, 403))
        self.assertIn(r2.status_code, (200, 302, 403))
        mock_delete.delay.assert_not_called()

    def test_post_with_delete_permission_is_accepted(self):
        """A staff user with explicit delete permission may queue deletion."""
        self._make_staff_user(with_delete_perm=True)
        self.client.logout()
        self.client.login(username="staff", password="staffpass123")

        with patch(self.delete_task_path) as mock_delete:
            response = self.client.post(
                self.changelist_url,
                data={
                    "action": "async_delete",
                    ACTION_CHECKBOX_NAME: [str(o.pk) for o in self.objects],
                    "post": "yes",
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_delete.delay.call_count, len(self.objects))

    def test_default_delete_selected_action_is_disabled(self):
        """
        The custom ``async_delete`` replaces Django's built-in
        ``delete_selected``; submitting the latter must not work.
        """
        with patch(self.delete_task_path) as mock_delete:
            response = self.client.post(
                self.changelist_url,
                data={
                    "action": "delete_selected",
                    ACTION_CHECKBOX_NAME: [str(o.pk) for o in self.objects],
                },
            )

        # Django re-renders the changelist (200) or redirects (302) when
        # the requested action was removed in get_actions().
        self.assertIn(response.status_code, (200, 302))
        mock_delete.delay.assert_not_called()
        for obj in self.objects:
            self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())


class AsyncDeleteDataModelAdminTests(AsyncDeleteAdminTestMixin, TestCase):
    model_name = "DataModel"
    model_class = DataModel

    @property
    def changelist_url(self):
        return reverse("admin:datasets_datamodel_changelist")

    def create_objects(self):
        return [
            DataModel.objects.create(name="Model A"),
            DataModel.objects.create(name="Model B"),
            DataModel.objects.create(name="Model C"),
        ]


class AsyncDeleteScenarioAdminTests(AsyncDeleteAdminTestMixin, TestCase):
    model_name = "Scenario"
    model_class = Scenario

    @property
    def changelist_url(self):
        return reverse("admin:datasets_scenario_changelist")

    def create_objects(self):
        dataset = VectorDataset.objects.create(
            name="Boundaries",
            created_by=self.superadmin,
            last_updated_by=self.superadmin,
            is_public=True,
            is_approved=True,
        )
        model = DataModel.objects.create(name="Test Model")
        return [
            Scenario.objects.create(
                name="Scenario A", model=model, vector_dataset=dataset
            ),
            Scenario.objects.create(
                name="Scenario B", model=model, vector_dataset=dataset
            ),
        ]
