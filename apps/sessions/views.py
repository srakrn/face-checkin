"""
Session views — detail and report pages.
These are stub implementations; full UI to be built in a later task.
"""

import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .models import Session


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
    """GET /api/sessions/<pk>/report/ — return check-in report."""
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
