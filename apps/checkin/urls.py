"""API URL routes for the checkin app."""

from django.urls import path

from . import views

app_name = "checkin_api"

urlpatterns = [
    path("checkin/match/", views.checkin_match, name="match"),
    # Session detail and report are in apps.sessions.urls
]
