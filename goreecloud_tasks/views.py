"""Small application-level views that do not belong to a domain app."""

from django.http import JsonResponse


def health(request):
    """Return a deliberately non-sensitive application health response."""
    return JsonResponse({"status": "ok"})
