"""
Tests for the auto_close_sessions management command
(apps/sessions/management/commands/auto_close_sessions.py).

Covers:
- Closes sessions past auto_close_at
- Does NOT close sessions before auto_close_at
- Does NOT touch already-closed sessions
"""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.classes.models import Class
from apps.faces.models import FaceGroup
from apps.sessions.models import Session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def face_group(db):
    return FaceGroup.objects.create(name="Test Group")


@pytest.fixture
def klass(face_group):
    return Class.objects.create(name="Test Class", face_group=face_group)


def _make_active_session(klass, name: str, auto_close_at=None) -> Session:
    return Session.objects.create(
        klass=klass,
        name=name,
        auto_close_at=auto_close_at,
    )


def _make_closed_session(klass, name: str, auto_close_at=None) -> Session:
    session = _make_active_session(klass, name, auto_close_at)
    session.close()
    return session


def _run_command() -> str:
    """Run auto_close_sessions and return stdout."""
    out = StringIO()
    call_command("auto_close_sessions", stdout=out)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAutoCloseSessions:
    def test_closes_active_session_past_auto_close_at(self, klass):
        past = timezone.now() - timedelta(minutes=5)
        session = _make_active_session(klass, "Overdue", auto_close_at=past)

        _run_command()

        session.refresh_from_db()
        assert session.state == Session.State.CLOSED

    def test_does_not_close_active_session_before_auto_close_at(self, klass):
        future = timezone.now() + timedelta(hours=1)
        session = _make_active_session(klass, "Future", auto_close_at=future)

        _run_command()

        session.refresh_from_db()
        assert session.state == Session.State.ACTIVE

    def test_does_not_close_active_session_without_auto_close_at(self, klass):
        session = _make_active_session(klass, "No AutoClose", auto_close_at=None)

        _run_command()

        session.refresh_from_db()
        assert session.state == Session.State.ACTIVE

    def test_does_not_touch_already_closed_session(self, klass):
        past = timezone.now() - timedelta(minutes=5)
        session = _make_closed_session(klass, "Already Closed", auto_close_at=past)

        _run_command()

        session.refresh_from_db()
        assert session.state == Session.State.CLOSED

    def test_closes_multiple_overdue_sessions(self, klass):
        past = timezone.now() - timedelta(minutes=5)
        s1 = _make_active_session(klass, "Overdue 1", auto_close_at=past)
        s2 = _make_active_session(klass, "Overdue 2", auto_close_at=past)
        s3 = _make_active_session(klass, "Overdue 3", auto_close_at=past)

        _run_command()

        for s in [s1, s2, s3]:
            s.refresh_from_db()
            assert s.state == Session.State.CLOSED

    def test_only_closes_overdue_sessions_not_future_ones(self, klass):
        past = timezone.now() - timedelta(minutes=5)
        future = timezone.now() + timedelta(hours=1)
        overdue = _make_active_session(klass, "Overdue", auto_close_at=past)
        upcoming = _make_active_session(klass, "Upcoming", auto_close_at=future)

        _run_command()

        overdue.refresh_from_db()
        upcoming.refresh_from_db()
        assert overdue.state == Session.State.CLOSED
        assert upcoming.state == Session.State.ACTIVE

    def test_command_outputs_closed_count(self, klass):
        past = timezone.now() - timedelta(minutes=5)
        _make_active_session(klass, "Overdue 1", auto_close_at=past)
        _make_active_session(klass, "Overdue 2", auto_close_at=past)

        output = _run_command()

        assert "2" in output

    def test_command_outputs_zero_when_nothing_to_close(self, klass):
        output = _run_command()
        assert "0" in output

    def test_command_mentions_closed_session_name_in_output(self, klass):
        past = timezone.now() - timedelta(minutes=5)
        _make_active_session(klass, "My Special Session", auto_close_at=past)

        output = _run_command()

        assert "My Special Session" in output
