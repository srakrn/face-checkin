"""Management UI URL routes for the sessions app."""

from django.urls import path

from . import views

app_name = "sessions"

urlpatterns = [
    # Session management UI
    path("", views.session_list, name="index"),
    path("classes/<int:class_pk>/", views.class_session_list, name="class_session_list"),
    path("checkins/<int:pk>/image/", views.checkin_image, name="checkin_image"),
    path("checkins/<int:pk>/remap/", views.checkin_remap, name="checkin_remap"),
    path("checkins/<int:pk>/delete/", views.checkin_delete, name="checkin_delete"),
    path("<int:pk>/open/", views.session_open, name="open"),
    path("<int:pk>/close/", views.session_close, name="close"),
    path("<int:pk>/report/", views.session_report_page, name="report_page"),
    path("<int:pk>/report/csv/", views.session_report_csv, name="report_csv"),
]
