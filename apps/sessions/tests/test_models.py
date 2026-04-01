"""
Unit tests for the Session state machine (apps/sessions/models.py).

Covers:
- Default state is active
- Valid transition: active → closed
- Invalid transitions raise ValueError
- should_auto_close property
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.classes.models import Course
from apps.faces.models import FaceGroup
from apps.sessions.models import Session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def face_group(db):
    return FaceGroup.objects.create(name="Test Group")


@pytest.fixture
def course(face_group):
    return Course.objects.create(name="Test Course", shorthand="TST", face_group=face_group)


@pytest.fixture
def active_session(course):
    return Session.objects.create(course=course, name="Test Session")


@pytest.fixture
def closed_session(active_session):
    active_session.close()
    return active_session


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSessionInitialState:
    def test_new_session_is_active(self, active_session):
        assert active_session.state == Session.State.ACTIVE

    def test_str_includes_state(self, active_session):
        assert "active" in str(active_session)


# ---------------------------------------------------------------------------
# Valid transitions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestValidTransitions:
    def test_active_to_closed(self, active_session):
        active_session.close()
        active_session.refresh_from_db()
        assert active_session.state == Session.State.CLOSED

    def test_close_persists_to_db(self, active_session):
        active_session.close()
        reloaded = Session.objects.get(pk=active_session.pk)
        assert reloaded.state == Session.State.CLOSED

    def test_closed_to_active(self, closed_session):
        closed_session.open()
        closed_session.refresh_from_db()
        assert closed_session.state == Session.State.ACTIVE

    def test_open_persists_to_db(self, closed_session):
        closed_session.open()
        reloaded = Session.objects.get(pk=closed_session.pk)
        assert reloaded.state == Session.State.ACTIVE


# ---------------------------------------------------------------------------
# Invalid transitions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestInvalidTransitions:
    def test_close_closed_session_raises(self, closed_session):
        with pytest.raises(ValueError, match="close"):
            closed_session.close()

    def test_open_active_session_raises(self, active_session):
        with pytest.raises(ValueError, match="open"):
            active_session.open()

    def test_invalid_transition_does_not_change_state(self, closed_session):
        """State must remain unchanged after a failed transition."""
        try:
            closed_session.close()
        except ValueError:
            pass
        closed_session.refresh_from_db()
        assert closed_session.state == Session.State.CLOSED


# ---------------------------------------------------------------------------
# should_auto_open property
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestShouldAutoOpen:
    def test_closed_session_past_scheduled_at_returns_true(self, closed_session):
        closed_session.scheduled_at = timezone.now() - timedelta(minutes=1)
        closed_session.save()
        assert closed_session.should_auto_open is True

    def test_closed_session_future_scheduled_at_returns_false(self, closed_session):
        closed_session.scheduled_at = timezone.now() + timedelta(hours=1)
        closed_session.save()
        assert closed_session.should_auto_open is False

    def test_closed_session_no_scheduled_at_returns_false(self, closed_session):
        closed_session.scheduled_at = None
        closed_session.save()
        assert closed_session.should_auto_open is False

    def test_active_session_past_scheduled_at_returns_false(self, active_session):
        """Only closed sessions can be auto-opened."""
        active_session.scheduled_at = timezone.now() - timedelta(minutes=1)
        active_session.save()
        assert active_session.should_auto_open is False

    def test_auto_open_at_exactly_now_returns_true(self, closed_session):
        """Boundary: scheduled_at == now should trigger auto-open."""
        now = timezone.now()
        closed_session.scheduled_at = now
        closed_session.save()
        assert closed_session.scheduled_at <= timezone.now()
        assert closed_session.should_auto_open is True

    def test_closed_session_past_auto_close_at_returns_false(self, closed_session):
        closed_session.scheduled_at = timezone.now() - timedelta(hours=2)
        closed_session.auto_close_at = timezone.now() - timedelta(hours=1)
        closed_session.save()
        assert closed_session.should_auto_open is False


# ---------------------------------------------------------------------------
# should_auto_close property
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestShouldAutoClose:
    def test_active_session_past_auto_close_at_returns_true(self, active_session):
        active_session.auto_close_at = timezone.now() - timedelta(minutes=1)
        active_session.save()
        assert active_session.should_auto_close is True

    def test_active_session_future_auto_close_at_returns_false(self, active_session):
        active_session.auto_close_at = timezone.now() + timedelta(hours=1)
        active_session.save()
        assert active_session.should_auto_close is False

    def test_active_session_no_auto_close_at_returns_false(self, active_session):
        active_session.auto_close_at = None
        active_session.save()
        assert active_session.should_auto_close is False

    def test_closed_session_past_auto_close_at_returns_false(self, closed_session):
        closed_session.auto_close_at = timezone.now() - timedelta(minutes=1)
        closed_session.save()
        assert closed_session.should_auto_close is False

    def test_auto_close_at_exactly_now_returns_true(self, active_session):
        """Boundary: auto_close_at == now should trigger auto-close."""
        now = timezone.now()
        active_session.auto_close_at = now
        active_session.save()
        # Patch timezone.now to return the same instant
        assert active_session.auto_close_at <= timezone.now()
        assert active_session.should_auto_close is True
