"""
Integration tests for session API views (apps/sessions/views.py).

Covers:
- session_detail: returns correct JSON for existing session, 404 for missing
- session_report: lists all check-ins with correct fields
"""

import io
import json

import numpy as np
import pytest
from django.test import Client
from django.utils import timezone

from apps.checkin.models import CheckIn
from apps.classes.models import Class
from apps.faces.models import Face, FaceGroup
from apps.sessions.models import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_embedding_bytes(vec: list[float]) -> bytes:
    return np.array(vec, dtype=np.float32).tobytes()


def _unit_vec(dim: int, index: int) -> list[float]:
    v = [0.0] * dim
    v[index] = 1.0
    return v


def _fake_image(name: str = "face.jpg") -> io.BytesIO:
    buf = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    buf.name = name
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    return Client()


@pytest.fixture
def face_group(db):
    return FaceGroup.objects.create(name="Test Group")


@pytest.fixture
def klass(face_group):
    return Class.objects.create(name="Test Class", face_group=face_group)


@pytest.fixture
def draft_session(klass):
    return Session.objects.create(klass=klass, name="Draft Session")


@pytest.fixture
def active_session(klass):
    return Session.objects.create(klass=klass, name="Active Session")


@pytest.fixture
def enrolled_face(face_group):
    return Face.objects.create(
        face_group=face_group,
        name="Alice",
        custom_id="alice-001",
        embedding=_make_embedding_bytes(_unit_vec(128, 0)),
    )


@pytest.fixture
def checkin_matched(active_session, enrolled_face):
    checkin = CheckIn(
        session=active_session,
        face=enrolled_face,
        matched=True,
    )
    checkin.raw_face_image.save("test.jpg", _fake_image(), save=False)
    checkin.save()
    return checkin


@pytest.fixture
def checkin_unmatched(active_session):
    checkin = CheckIn(
        session=active_session,
        face=None,
        matched=False,
    )
    checkin.raw_face_image.save("test_unmatched.jpg", _fake_image(), save=False)
    checkin.save()
    return checkin


# ---------------------------------------------------------------------------
# GET /api/sessions/<pk>/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSessionDetail:
    def test_returns_200_for_existing_session(self, client, draft_session):
        response = client.get(f"/api/sessions/{draft_session.pk}/")
        assert response.status_code == 200

    def test_returns_correct_id(self, client, draft_session):
        response = client.get(f"/api/sessions/{draft_session.pk}/")
        data = response.json()
        assert data["id"] == draft_session.pk

    def test_returns_correct_name(self, client, draft_session):
        response = client.get(f"/api/sessions/{draft_session.pk}/")
        data = response.json()
        assert data["name"] == "Draft Session"

    def test_returns_correct_state_active(self, client, active_session):
        response = client.get(f"/api/sessions/{active_session.pk}/")
        data = response.json()
        assert data["state"] == "active"

    def test_returns_correct_class_id(self, client, draft_session, klass):
        response = client.get(f"/api/sessions/{draft_session.pk}/")
        data = response.json()
        assert data["class_id"] == klass.pk

    def test_scheduled_at_none_when_not_set(self, client, draft_session):
        response = client.get(f"/api/sessions/{draft_session.pk}/")
        data = response.json()
        assert data["scheduled_at"] is None

    def test_auto_close_at_none_when_not_set(self, client, draft_session):
        response = client.get(f"/api/sessions/{draft_session.pk}/")
        data = response.json()
        assert data["auto_close_at"] is None

    def test_returns_404_for_nonexistent_session(self, client, db):
        response = client.get("/api/sessions/999999/")
        assert response.status_code == 404

    def test_post_method_not_allowed(self, client, draft_session):
        response = client.post(f"/api/sessions/{draft_session.pk}/")
        assert response.status_code == 405


# ---------------------------------------------------------------------------
# GET /api/sessions/<pk>/report/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSessionReport:
    def test_returns_200_for_existing_session(self, client, active_session):
        response = client.get(f"/api/sessions/{active_session.pk}/report/")
        assert response.status_code == 200

    def test_returns_correct_session_id(self, client, active_session):
        response = client.get(f"/api/sessions/{active_session.pk}/report/")
        data = response.json()
        assert data["session_id"] == active_session.pk

    def test_empty_checkins_list_when_no_checkins(self, client, active_session):
        response = client.get(f"/api/sessions/{active_session.pk}/report/")
        data = response.json()
        assert data["checkins"] == []

    def test_lists_all_checkins(
        self, client, active_session, checkin_matched, checkin_unmatched
    ):
        response = client.get(f"/api/sessions/{active_session.pk}/report/")
        data = response.json()
        assert len(data["checkins"]) == 2

    def test_matched_checkin_has_correct_fields(
        self, client, active_session, checkin_matched, enrolled_face
    ):
        response = client.get(f"/api/sessions/{active_session.pk}/report/")
        data = response.json()
        matched = next(c for c in data["checkins"] if c["matched"])
        assert matched["face_id"] == enrolled_face.pk
        assert matched["face_name"] == "Alice"
        assert matched["face_custom_id"] == "alice-001"
        assert "checked_in_at" in matched

    def test_unmatched_checkin_has_null_face_fields(
        self, client, active_session, checkin_unmatched
    ):
        response = client.get(f"/api/sessions/{active_session.pk}/report/")
        data = response.json()
        unmatched = next(c for c in data["checkins"] if not c["matched"])
        assert unmatched["face_id"] is None
        assert unmatched["face_name"] is None
        assert unmatched["face_custom_id"] is None

    def test_returns_404_for_nonexistent_session(self, client, db):
        response = client.get("/api/sessions/999999/report/")
        assert response.status_code == 404

    def test_post_method_not_allowed(self, client, active_session):
        response = client.post(f"/api/sessions/{active_session.pk}/report/")
        assert response.status_code == 405
