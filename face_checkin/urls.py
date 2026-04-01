"""
URL configuration for face_checkin project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import messages
from django.contrib import admin
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import include, path
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView
from django.views.decorators.http import require_http_methods, require_POST


def health_check(request):
    """Simple health check endpoint for Docker and monitoring."""
    return JsonResponse({"status": "ok"})


def _get_safe_redirect_target(request, default: str = "/") -> str:
    candidate = request.POST.get("next") or request.GET.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return default


def index(request):
    if not request.user.is_authenticated:
        return render(request, "landing.html")

    from apps.classes.models import Course
    from apps.sessions.models import Session

    active_sessions = (
        Session.objects.filter(state="active")
        .select_related("course")
        .order_by("-scheduled_at")
    )
    if not request.user.is_superuser:
        active_sessions = active_sessions.filter(course__in=Course.objects.accessible_to(request.user)).distinct()

    return render(request, "index.html", {"active_sessions": active_sessions})


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect(_get_safe_redirect_target(request))

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_active:
            auth_login(request, user)
            return redirect(_get_safe_redirect_target(request))

        messages.error(request, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

    return render(
        request,
        "login.html",
        {"next_url": _get_safe_redirect_target(request)},
    )


@require_POST
def logout_view(request):
    auth_logout(request)
    messages.success(request, "ออกจากระบบแล้ว")
    return redirect("index")


urlpatterns = [
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path("", index, name="index"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
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
