"""
Session views — API endpoints + HTMX-powered management UI.
"""

import csv
from datetime import datetime
from urllib.parse import urlencode

from apps.checkin.anomaly import detect_anomalies
from apps.checkin.models import CheckIn
from apps.classes.models import Course
from apps.faces.models import Face

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from .models import Session


def _accessible_classes(user):
    queryset = Course.objects.all()
    if user.is_superuser:
        return queryset
    return Course.objects.accessible_to(user)


def _accessible_sessions(user):
    queryset = Session.objects.select_related("course", "course__face_group")
    if user.is_superuser:
        return queryset
    return queryset.filter(course__in=Course.objects.accessible_to(user)).distinct()


def _accessible_checkins(user):
    queryset = CheckIn.objects.select_related("session", "session__course", "session__course__face_group", "face")
    if user.is_superuser:
        return queryset
    return queryset.filter(session__course__in=Course.objects.accessible_to(user)).distinct()


SESSION_SORT_OPTIONS = {
    "default": None,
    "name_asc": ["name", "pk"],
    "name_desc": ["-name", "-pk"],
    "scheduled_asc": ["scheduled_at", "pk"],
    "scheduled_desc": ["-scheduled_at", "-pk"],
    "auto_close_asc": ["auto_close_at", "pk"],
    "auto_close_desc": ["-auto_close_at", "-pk"],
    "created_asc": ["created_at", "pk"],
    "created_desc": ["-created_at", "-pk"],
}

REPORT_SORT_OPTIONS = {
    "default": "default",
    "time_asc": "default",
    "time_desc": "time_desc",
    "name_asc": "name_asc",
    "name_desc": "name_desc",
}


def _clean_query_value(value: str | None) -> str:
    return (value or "").strip()


def _query_string(params: dict[str, str]) -> str:
    filtered = {key: value for key, value in params.items() if value not in ("", None, "all", "default")}
    return urlencode(filtered)


def _sort_meta(current_sort: str, asc_value: str, desc_value: str) -> dict[str, str | bool]:
    if current_sort == asc_value:
        return {"active": True, "descending": False, "indicator": "↑", "next": desc_value}
    if current_sort == desc_value:
        return {"active": True, "descending": True, "indicator": "↓", "next": asc_value}
    return {"active": False, "descending": False, "indicator": "↕", "next": asc_value}


def _session_list_filters(request):
    q = _clean_query_value(request.GET.get("q"))
    state = request.GET.get("state", "all")
    sort = request.GET.get("sort", "default")

    if state not in {"all", Session.State.ACTIVE, Session.State.CLOSED}:
        state = "all"
    if sort not in SESSION_SORT_OPTIONS:
        sort = "default"

    return {"q": q, "state": state, "sort": sort}


def _report_filters(request):
    q = _clean_query_value(request.GET.get("q"))
    matched = request.GET.get("matched", "all")
    anomaly = request.GET.get("anomaly", "all")
    sort = request.GET.get("sort", "default")
    unique_only = request.GET.get("unique") == "1"

    if matched not in {"all", "matched", "unmatched"}:
        matched = "all"
    if anomaly not in {"all", "suspicious_only", "normal_only"}:
        anomaly = "all"
    if sort not in REPORT_SORT_OPTIONS:
        sort = "default"

    return {
        "q": q,
        "matched": matched,
        "anomaly": anomaly,
        "sort": sort,
        "unique": "1" if unique_only else "",
        "unique_only": unique_only,
    }


def _apply_session_list_filters(sessions, filters):
    if filters["q"]:
        sessions = sessions.filter(name__icontains=filters["q"])
    if filters["state"] != "all":
        sessions = sessions.filter(state=filters["state"])

    order_by = SESSION_SORT_OPTIONS[filters["sort"]]
    if order_by:
        sessions = sessions.order_by(*order_by)
    return sessions


def _apply_report_filters(checkins, anomalies, filters):
    if filters["q"]:
        query = filters["q"]
        checkins = [
            checkin
            for checkin in checkins
            if checkin.face
            and (
                query.casefold() in (checkin.face.name or "").casefold()
                or query.casefold() in (checkin.face.custom_id or "").casefold()
            )
        ]

    if filters["matched"] == "matched":
        checkins = [checkin for checkin in checkins if checkin.matched]
    elif filters["matched"] == "unmatched":
        checkins = [checkin for checkin in checkins if not checkin.matched]

    if filters["anomaly"] == "suspicious_only":
        checkins = [checkin for checkin in checkins if anomalies.get(checkin.pk)]
    elif filters["anomaly"] == "normal_only":
        checkins = [checkin for checkin in checkins if not anomalies.get(checkin.pk)]

    if filters["sort"] == "time_desc":
        checkins = sorted(checkins, key=lambda checkin: (checkin.checked_in_at, checkin.pk), reverse=True)
    elif filters["sort"] == "name_asc":
        checkins = sorted(
            checkins,
            key=lambda checkin: (
                checkin.face is None,
                (checkin.face.name or "").casefold() if checkin.face else "",
                checkin.pk,
            ),
        )
    elif filters["sort"] == "name_desc":
        checkins = sorted(
            checkins,
            key=lambda checkin: (
                checkin.face is not None,
                (checkin.face.name or "").casefold() if checkin.face else "",
                checkin.pk,
            ),
            reverse=True,
        )

    return checkins


def _report_query_params(filters: dict[str, str]) -> dict[str, str]:
    return {
        "unique": filters.get("unique", ""),
        "q": filters.get("q", ""),
        "matched": filters.get("matched", "all"),
        "anomaly": filters.get("anomaly", "all"),
        "sort": filters.get("sort", "default"),
    }


def _session_list_query_params(filters: dict[str, str]) -> dict[str, str]:
    return {
        "q": filters.get("q", ""),
        "state": filters.get("state", "all"),
        "sort": filters.get("sort", "default"),
    }


# ---------------------------------------------------------------------------
# API views (JSON) — used by the kiosk
# ---------------------------------------------------------------------------


@require_GET
@login_required
def session_detail(request, pk: int):
    """GET /api/sessions/<pk>/ — return session state and metadata."""
    session = get_object_or_404(_accessible_sessions(request.user), pk=pk)
    return JsonResponse(
        {
            "id": session.pk,
            "name": session.name,
            "state": session.state,
            "scheduled_at": session.scheduled_at.isoformat() if session.scheduled_at else None,
            "auto_close_at": session.auto_close_at.isoformat() if session.auto_close_at else None,
            "course_id": session.course_id,
        }
    )


@require_GET
@login_required
def session_report(request, pk: int):
    """GET /api/sessions/<pk>/report/ — return check-in report as JSON."""
    session = get_object_or_404(_accessible_sessions(request.user), pk=pk)
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
def course_session_list(request, course_pk: int):
    """GET /courses/<course_pk>/sessions/ — list all sessions for a course."""
    course = get_object_or_404(_accessible_classes(request.user), pk=course_pk)
    filters = _session_list_filters(request)
    sessions = _apply_session_list_filters(course.sessions.all(), filters)
    all_courses = _accessible_classes(request.user).order_by("name")
    session_sort_links = {}
    for key, asc_value, desc_value in (
        ("name", "name_asc", "name_desc"),
        ("scheduled", "scheduled_asc", "scheduled_desc"),
        ("auto_close", "auto_close_asc", "auto_close_desc"),
    ):
        meta = _sort_meta(filters["sort"], asc_value, desc_value)
        session_sort_links[key] = {
            **meta,
            "query": _query_string({**_session_list_query_params(filters), "sort": meta["next"]}),
        }
    return render(
        request,
        "sessions/session_list.html",
        {
            "course": course,
            "sessions": sessions,
            "all_courses": all_courses,
            "filters": filters,
            "has_active_filters": any(value not in ("", "all", "default") for value in filters.values()),
            "session_sort_links": session_sort_links,
        },
    )


@login_required
def session_list(request):
    """GET /courses/ — list all courses (entry point for session management)."""
    all_courses = _accessible_classes(request.user).prefetch_related("sessions").order_by("name")
    return render(
        request,
        "sessions/index.html",
        {"all_courses": all_courses},
    )


@login_required
@require_POST
def session_open(request, pk: int):
    """POST /sessions/<pk>/open/ — open a closed session (HTMX)."""
    session = get_object_or_404(_accessible_sessions(request.user), pk=pk)
    try:
        session.open()
    except ValueError as exc:
        return HttpResponse(str(exc), status=400)
    return render(request, "sessions/partials/session_row.html", {"session": session})


@login_required
@require_POST
def session_close(request, pk: int):
    """POST /sessions/<pk>/close/ — close an active session (HTMX)."""
    session = get_object_or_404(_accessible_sessions(request.user), pk=pk)
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


def _report_page_url(session_pk: int, unique_only: bool) -> str:
    url = reverse("sessions:report_page", args=[session_pk])
    if unique_only:
        return f"{url}?unique=1"
    return url


def _report_page_url_with_filters(session_pk: int, filters: dict[str, str]) -> str:
    url = reverse("sessions:report_page", args=[session_pk])
    query = _query_string(_report_query_params(filters))
    if not query:
        return url
    return f"{url}?{query}"


@login_required
def session_report_page(request, pk: int):
    """GET /sessions/<pk>/report/ — HTML report page for a session."""
    session = get_object_or_404(_accessible_sessions(request.user), pk=pk)
    filters = _report_filters(request)
    unique_only = filters["unique_only"]
    all_checkins = list(session.checkins.select_related("face").order_by("checked_in_at"))
    checkins = _deduplicate_checkins(all_checkins) if unique_only else list(all_checkins)
    face_options = list(session.course.face_group.faces.order_by("custom_id", "name"))
    anomalies = detect_anomalies(checkins)
    checkins = _apply_report_filters(checkins, anomalies, filters)
    matched_count = sum(1 for c in checkins if c.matched)
    unmatched_count = len(checkins) - matched_count
    anomaly_count = sum(1 for c in checkins if anomalies.get(c.pk))
    # Annotate each checkin with its anomaly reasons for easy template access
    for c in checkins:
        c.anomaly_reasons = anomalies.get(c.pk, [])

    current_report_query = _query_string(_report_query_params(filters))
    toggle_unique_filters = {**filters, "unique": "" if unique_only else "1"}
    report_sort_links = {}
    for key, asc_value, desc_value in (
        ("name", "name_asc", "name_desc"),
        ("time", "default", "time_desc"),
    ):
        meta = _sort_meta(filters["sort"], asc_value, desc_value)
        report_sort_links[key] = {
            **meta,
            "query": _query_string({**_report_query_params(filters), "sort": meta["next"]}),
        }
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
            "face_options": face_options,
            "filters": filters,
            "has_active_filters": any(
                filters[key] not in ("", "all", "default")
                for key in ("q", "matched", "anomaly", "sort")
            ),
            "report_csv_query": current_report_query,
            "toggle_unique_query": _query_string(_report_query_params(toggle_unique_filters)),
            "reset_report_query": _query_string({"unique": filters["unique"]}),
            "report_action_params": _report_query_params(filters),
            "report_sort_links": report_sort_links,
        },
    )


@login_required
def session_report_csv(request, pk: int):
    """GET /sessions/<pk>/report/csv/ — download check-in report as CSV."""
    session = get_object_or_404(_accessible_sessions(request.user), pk=pk)
    filters = _report_filters(request)
    unique_only = filters["unique_only"]
    all_checkins = list(session.checkins.select_related("face").order_by("checked_in_at"))
    checkins = _deduplicate_checkins(all_checkins) if unique_only else list(all_checkins)
    anomalies = detect_anomalies(checkins)
    checkins = _apply_report_filters(checkins, anomalies, filters)

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
    checkin = get_object_or_404(_accessible_checkins(request.user), pk=pk)
    image_field = checkin.raw_face_image
    image_field.open("rb")
    return FileResponse(image_field, content_type="image/jpeg")


@login_required
@require_POST
def checkin_remap(request, pk: int):
    """POST /sessions/checkins/<pk>/remap/ — remap a check-in to a face in the session face group."""
    checkin = get_object_or_404(_accessible_checkins(request.user), pk=pk)
    filters = _report_query_params(request.POST)
    face_id = request.POST.get("face_id")

    if not face_id:
        messages.error(request, _("Please choose a participant."))
        return redirect(_report_page_url_with_filters(checkin.session_id, filters))

    face = get_object_or_404(
        Face,
        pk=face_id,
        face_group=checkin.session.course.face_group,
    )

    checkin.face = face
    checkin.matched = True
    checkin.save(update_fields=["face", "matched"])

    messages.success(request, _('Check-in remapped to "%(name)s".') % {"name": face.name})
    return redirect(_report_page_url_with_filters(checkin.session_id, filters))


@login_required
@require_POST
def checkin_manual(request, pk: int):
    """POST /sessions/<pk>/checkins/manual/ — create a manual check-in for a participant."""
    session = get_object_or_404(_accessible_sessions(request.user), pk=pk)
    filters = _report_query_params(request.POST)
    face_id = request.POST.get("face_id")
    checked_in_at_str = request.POST.get("checked_in_at")

    if not face_id:
        messages.error(request, _("Please choose a participant."))
        return redirect(_report_page_url_with_filters(pk, filters))

    face = get_object_or_404(
        Face,
        pk=face_id,
        face_group=session.course.face_group,
    )

    if checked_in_at_str:
        try:
            checked_in_at = datetime.fromisoformat(checked_in_at_str)
            if timezone.is_naive(checked_in_at):
                checked_in_at = timezone.make_aware(checked_in_at)
        except ValueError:
            checked_in_at = timezone.now()
    else:
        checked_in_at = timezone.now()

    checkin = CheckIn.objects.create(session=session, face=face, matched=True)
    # auto_now_add prevents passing checked_in_at at creation time; update it directly.
    CheckIn.objects.filter(pk=checkin.pk).update(checked_in_at=checked_in_at)

    messages.success(request, _('Manual check-in created for "%(name)s".') % {"name": face.name})
    return redirect(_report_page_url_with_filters(pk, filters))


@login_required
@require_POST
def checkin_delete(request, pk: int):
    """POST /sessions/checkins/<pk>/delete/ — delete a check-in from the report."""
    checkin = get_object_or_404(_accessible_checkins(request.user), pk=pk)
    filters = _report_query_params(request.POST)
    session_id = checkin.session_id
    if checkin.raw_face_image:
        checkin.raw_face_image.delete(save=False)
    checkin.delete()
    messages.success(request, _("Check-in deleted."))
    return redirect(_report_page_url_with_filters(session_id, filters))
