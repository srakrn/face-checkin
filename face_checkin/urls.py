"""
URL configuration for face_checkin project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.checkin.urls")),
    path("sessions/", include("apps.sessions.urls")),
    path("", include("apps.checkin.kiosk_urls")),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns

    if not settings.USE_S3:
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
