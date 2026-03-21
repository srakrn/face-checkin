"""
URL configuration for face_checkin project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health_check(request):
    """Simple health check endpoint for Docker and monitoring."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("admin/", admin.site.urls),
    # Checkin API (match + embeddings)
    path("api/", include("apps.checkin.urls")),
    # Sessions JSON API (detail + report)
    path("api/sessions/", include("apps.sessions.api_urls")),
    # Session management UI (HTMX)
    path("sessions/", include("apps.sessions.urls")),
    # Kiosk HTML page
    path("", include("apps.checkin.kiosk_urls")),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns

    if not settings.USE_S3:
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
