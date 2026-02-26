"""JSON API URL routes for the sessions app (used by the kiosk)."""

from django.urls import path

from . import views

app_name = "sessions_api"

urlpatterns = [
    path("<int:pk>/", views.session_detail, name="detail"),
    path("<int:pk>/report/", views.session_report, name="report"),
]
