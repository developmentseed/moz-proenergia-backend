import os
from celery import Celery
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Set the default Django settings module for the 'celery' program.
# This project uses django-configurations, so we need to set both variables.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "proenergia.config")
os.environ.setdefault("DJANGO_CONFIGURATION", "Local")

# This import must come after setting the environment variables
import configurations

configurations.setup()

app = Celery("proenergia")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configuration for connection retry
app.conf.broker_connection_retry_on_startup = True


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
