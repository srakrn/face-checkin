"""
Kiosk HTML view — renders the check-in page for a given session.
The page uses AlpineJS + HTMX + face-api.js for on-device face capture.
"""

from django.shortcuts import get_object_or_404, render

from apps.sessions.models import Session


def kiosk(request, session_id: int):
    """Render the kiosk check-in page for an active session."""
    session = get_object_or_404(Session, pk=session_id)
    return render(
        request,
        "checkin/kiosk.html",
        {
            "session": session,
            "session_active": session.state == Session.State.ACTIVE,
        },
    )
