"""
Tests for the auto_open_sessions management command
(apps/sessions/management/commands/auto_open_sessions.py).

Covers:
- Opens closed sessions past scheduled_at
- Does NOT open closed sessions before scheduled_at
- Does NOT open closed sessions without scheduled_at
- Does NOT touch already-active sessions
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


def _make_closed_session(klass, name: str, scheduled_at=None) -> Session:
    session = Session.objects.create(
        klass=klass,
        name=name,
        scheduled_at=scheduled_at,
    )
    session.close()
    return session


def _make_active_session(klass, name: str, scheduled_at=None) -> Session:
    return Session.objects.create(
        klass=klass,
        name=name,
        scheduled_at=scheduled_at,
    )


def _run_command() -> str:
    """Run auto_open_sessions and return stdout."""
    out = StringIO()
    call_command("auto_open_sessions", stdout=out)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAutoOpenSessions:
    def test_opens_closed_session_past_scheduled_at(self, klass):
        past = timezone.now() - timedelta(minutes=5)
        session = _make_closed_session(klass, "Overdue", scheduled_at=past)

        _run_command()

        session.refresh_from_db()
        assert session.state == Session.State.ACTIVE

    def test_does_not_open_closed_session_before_scheduled_at(self, klass):
        future = timezone.now() + timedelta(hours=1)
        session = _make_closed_session(klass, "Future", scheduled_at=future)

        _run_command()

        session.refresh_from_db()
        assert session.state == Session.State.CLOSED

    def test_does_not_reopen_session_after_auto_close_time_has_passed(self, klass):
        past_start = timezone.now() - timedelta(hours=2)
        past_end = timezone.now() - timedelta(hours=1)
        session = Session.objects.create(
            klass=klass,
            name="Expired Session",
            scheduled_at=past_start,
            auto_close_at=past_end,
        )
        session.close()

        _run_command()

        session.refresh_from_db()
        assert session.state == Session.State.CLOSED

    def test_does_not_open_closed_session_without_scheduled_at(self, klass):
        session = _make_closed_session(klass, "No Schedule", scheduled_at=None)

        _run_command()

        session.refresh_from_db()
        assert session.state == Session.State.CLOSED

    def test_does_not_touch_active_session(self, klass):
        past = timezone.now() - timedelta(minutes=5)
        session = _make_active_session(klass, "Already Active", scheduled_at=past)

        _run_command()

        session.refresh_from_db()
        assert session.state == Session.State.ACTIVE

    def test_opens_multiple_overdue_sessions(self, klass):
        past = timezone.now() - timedelta(minutes=5)
        s1 = _make_closed_session(klass, "Overdue 1", scheduled_at=past)
        s2 = _make_closed_session(klass, "Overdue 2", scheduled_at=past)
        s3 = _make_closed_session(klass, "Overdue 3", scheduled_at=past)

        _run_command()

        for s in [s1, s2, s3]:
            s.refresh_from_db()
            assert s.state == Session.State.ACTIVE

    def test_only_opens_overdue_sessions_not_future_ones(self, klass):
        past = timezone.now() - timedelta(minutes=5)
        future = timezone.now() + timedelta(hours=1)
        overdue = _make_closed_session(klass, "Overdue", scheduled_at=past)
        upcoming = _make_closed_session(klass, "Upcoming", scheduled_at=future)

        _run_command()

        overdue.refresh_from_db()
        upcoming.refresh_from_db()
        assert overdue.state == Session.State.ACTIVE
        assert upcoming.state == Session.State.CLOSED

    def test_command_outputs_opened_count(self, klass):
        past = timezone.now() - timedelta(minutes=5)
        _make_closed_session(klass, "Overdue 1", scheduled_at=past)
        _make_closed_session(klass, "Overdue 2", scheduled_at=past)

        output = _run_command()

        assert "2" in output

    def test_command_outputs_zero_when_nothing_to_open(self, klass):
        output = _run_command()
        assert "0" in output

    def test_command_mentions_opened_session_name_in_output(self, klass):
        past = timezone.now() - timedelta(minutes=5)
        _make_closed_session(klass, "My Special Session", scheduled_at=past)

        output = _run_command()

        assert "My Special Session" in output
