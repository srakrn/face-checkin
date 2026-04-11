"""Management UI URL routes for the sessions app."""

from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "sessions"

urlpatterns = [
    # Course-first management UI
    path("courses/", views.session_list, name="index"),
    path("courses/<int:course_pk>/sessions/", views.course_session_list, name="course_session_list"),
    # Backward-compatible redirect for the previous landing page URL
    path("sessions/", RedirectView.as_view(pattern_name="sessions:index", permanent=False)),
    # Session-specific actions and reports
    path("sessions/checkins/<int:pk>/image/", views.checkin_image, name="checkin_image"),
    path("sessions/checkins/<int:pk>/remap/", views.checkin_remap, name="checkin_remap"),
    path("sessions/checkins/<int:pk>/delete/", views.checkin_delete, name="checkin_delete"),
    path("sessions/<int:pk>/checkins/manual/", views.checkin_manual, name="checkin_manual"),
    path("sessions/<int:pk>/open/", views.session_open, name="open"),
    path("sessions/<int:pk>/close/", views.session_close, name="close"),
    path("sessions/<int:pk>/report/", views.session_report_page, name="report_page"),
    path("sessions/<int:pk>/report/csv/", views.session_report_csv, name="report_csv"),
]
