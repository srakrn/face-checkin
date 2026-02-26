"""
URL configuration for the faces app.
"""

from django.urls import path

from . import views

app_name = "faces"

urlpatterns = [
    # POST /faces/<pk>/enroll/  — save photo + embedding for a Face record
    path("<int:pk>/enroll/", views.enroll, name="enroll"),
]
