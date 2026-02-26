"""Kiosk-facing URL routes (HTML views)."""

from django.urls import path

from . import kiosk_views

app_name = "kiosk"

urlpatterns = [
    path("kiosk/<int:session_id>/", kiosk_views.kiosk, name="kiosk"),
]
