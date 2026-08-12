"""Per-user time-zone activation for task scheduling and reminders."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone


class UserTimezoneMiddleware:
    """Activate an authenticated user's stored IANA time zone for each request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        zone_name = settings.TIME_ZONE
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.timezone:
            zone_name = user.timezone

        try:
            timezone.activate(ZoneInfo(zone_name))
        except (ZoneInfoNotFoundError, ValueError):
            timezone.activate(ZoneInfo(settings.TIME_ZONE))

        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
