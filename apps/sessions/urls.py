from django.urls import path

from . import views

app_name = "sessions"

urlpatterns = [
    path("<int:pk>/", views.session_detail, name="detail"),
    path("<int:pk>/report/", views.session_report, name="report"),
]
