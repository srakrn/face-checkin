"""
Session views — API endpoints + HTMX-powered management UI.
"""

import csv
import json

from apps.checkin.anomaly import detect_anomalies
from apps.checkin.models import CheckIn

from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from apps.classes.models import Class

from .models import Session


# ---------------------------------------------------------------------------
# API views (JSON) — used by the kiosk
# ---------------------------------------------------------------------------


@require_GET
def session_detail(request, pk: int):
    """GET /api/sessions/<pk>/ — return session state and metadata."""
    session = get_object_or_404(Session, pk=pk)
    return JsonResponse(
        {
            "id": session.pk,
            "name": session.name,
            "state": session.state,
            "scheduled_at": session.scheduled_at.isoformat() if session.scheduled_at else None,
            "auto_close_at": session.auto_close_at.isoformat() if session.auto_close_at else None,
            "class_id": session.klass_id,
        }
    )


@require_GET
def session_report(request, pk: int):
    """GET /api/sessions/<pk>/report/ — return check-in report as JSON."""
    session = get_object_or_404(Session, pk=pk)
    checkins = session.checkins.select_related("face").order_by("checked_in_at")
    data = [
        {
            "id": c.pk,
            "matched": c.matched,
            "face_id": c.face_id,
            "face_name": c.face.name if c.face else None,
            "face_custom_id": c.face.custom_id if c.face else None,
            "checked_in_at": c.checked_in_at.isoformat(),
        }
        for c in checkins
    ]
    return JsonResponse({"session_id": pk, "checkins": data})


# ---------------------------------------------------------------------------
# Management UI views (HTML / HTMX)
# ---------------------------------------------------------------------------


@login_required
def class_session_list(request, class_pk: int):
    """GET /sessions/classes/<class_pk>/ — list all sessions for a class."""
    klass = get_object_or_404(Class, pk=class_pk)
    sessions = klass.sessions.all()
    all_classes = Class.objects.all().order_by("name")
    return render(
        request,
        "sessions/session_list.html",
        {
            "klass": klass,
            "sessions": sessions,
            "all_classes": all_classes,
        },
    )


@login_required
def session_list(request):
    """GET /sessions/ — list all classes (entry point for session management)."""
    all_classes = Class.objects.prefetch_related("sessions").order_by("name")
    return render(
        request,
        "sessions/index.html",
        {"all_classes": all_classes},
    )


@login_required
@require_POST
def session_close(request, pk: int):
    """POST /sessions/<pk>/close/ — close an active session (HTMX)."""
    session = get_object_or_404(Session, pk=pk)
    try:
        session.close()
    except ValueError as exc:
        return HttpResponse(str(exc), status=400)
    return render(request, "sessions/partials/session_row.html", {"session": session})


def _deduplicate_checkins(checkins):
    """Return only the first check-in per face (by face_id), preserving order."""
    seen = set()
    result = []
    for c in checkins:
        key = c.face_id  # None groups all unmatched together — keep them all
        if key is None or key not in seen:
            result.append(c)
            if key is not None:
                seen.add(key)
    return result


@login_required
def session_report_page(request, pk: int):
    """GET /sessions/<pk>/report/ — HTML report page for a session."""
    session = get_object_or_404(Session, pk=pk)
    unique_only = request.GET.get("unique") == "1"
    all_checkins = list(session.checkins.select_related("face").order_by("checked_in_at"))
    checkins = _deduplicate_checkins(all_checkins) if unique_only else all_checkins
    matched_count = sum(1 for c in checkins if c.matched)
    unmatched_count = len(checkins) - matched_count
    anomalies = detect_anomalies(checkins)
    anomaly_count = sum(1 for reasons in anomalies.values() if reasons)
    # Annotate each checkin with its anomaly reasons for easy template access
    for c in checkins:
        c.anomaly_reasons = anomalies.get(c.pk, [])
    return render(
        request,
        "sessions/report.html",
        {
            "session": session,
            "checkins": checkins,
            "matched_count": matched_count,
            "unmatched_count": unmatched_count,
            "anomaly_count": anomaly_count,
            "unique_only": unique_only,
            "total_checkin_count": len(all_checkins),
        },
    )


@login_required
def session_report_csv(request, pk: int):
    """GET /sessions/<pk>/report/csv/ — download check-in report as CSV."""
    session = get_object_or_404(Session, pk=pk)
    unique_only = request.GET.get("unique") == "1"
    all_checkins = list(session.checkins.select_related("face").order_by("checked_in_at"))
    checkins = _deduplicate_checkins(all_checkins) if unique_only else all_checkins
    anomalies = detect_anomalies(checkins)

    response = HttpResponse(content_type="text/csv")
    filename = f"session_{session.pk}_report.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(["#", "Name", "Custom ID", "Matched", "Checked In At", "IP Address", "User Agent", "Anomaly"])
    for i, c in enumerate(checkins, start=1):
        reasons = anomalies.get(c.pk, [])
        writer.writerow(
            [
                i,
                c.face.name if c.face else "",
                c.face.custom_id if c.face else "",
                "Yes" if c.matched else "No",
                c.checked_in_at.strftime("%Y-%m-%d %H:%M:%S"),
                c.ip_address or "",
                c.user_agent or "",
                "; ".join(reasons) if reasons else "",
            ]
        )
    return response


@login_required
@require_GET
def checkin_image(request, pk: int):
    """GET /sessions/checkins/<pk>/image/ — stream a check-in image to authenticated users."""
    checkin = get_object_or_404(CheckIn.objects.select_related("session"), pk=pk)
    image_field = checkin.raw_face_image
    image_field.open("rb")
    return FileResponse(image_field, content_type="image/jpeg")
