import pytest
from celery import current_app
from django.contrib.auth import get_user_model


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Enable database access for all tests.
    """
    pass


@pytest.fixture
def celery_eager():
    """
    Configure Celery to execute tasks synchronously for testing.
    """
    current_app.conf.task_always_eager = True
    current_app.conf.task_eager_propagates = True
    yield
    current_app.conf.task_always_eager = False
    current_app.conf.task_eager_propagates = False


@pytest.fixture
def test_user(db):
    """
    Create a test user.
    """
    User = get_user_model()
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )
