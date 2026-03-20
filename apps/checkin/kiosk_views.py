"""
Kiosk HTML view — renders the check-in page for a given session.
The page uses AlpineJS + face-api.js for on-device face capture.

Session state is passed to the template so the kiosk can display
appropriate error panels for closed / not-found sessions.
"""

from django.shortcuts import render

from apps.sessions.models import Session


def kiosk(request, session_id: int):
    """
    Render the kiosk check-in page for a session.

    Template context:
        session        — Session instance (or None if not found)
        session_state  — one of: "active" | "closed" | "not_found"
    """
    try:
        session = Session.objects.get(pk=session_id)
    except Session.DoesNotExist:
        return render(
            request,
            "checkin/kiosk.html",
            {"session": None, "session_state": "not_found"},
        )

    state_map = {
        Session.State.ACTIVE: "active",
        Session.State.CLOSED: "closed",
    }
    session_state = state_map.get(session.state, "closed")

    return render(
        request,
        "checkin/kiosk.html",
        {
            "session": session,
            "session_state": session_state,
        },
    )
