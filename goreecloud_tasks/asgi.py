"""ASGI entry point for GoreeCloud Tasks."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "goreecloud_tasks.settings")

application = get_asgi_application()
