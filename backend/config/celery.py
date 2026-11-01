import os

from celery import Celery


os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)

app = Celery("software_triage_team")

# Load configuration from Django settings.
# CELERY_ prefixed settings are recognized.
app.config_from_object(
    "django.conf:settings",
    namespace="CELERY",
)

# Automatically discover tasks.py in installed Django apps.
app.autodiscover_tasks()