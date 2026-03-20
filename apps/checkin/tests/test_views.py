"""
Integration tests for POST /api/checkin/match/ (apps/checkin/views.py).

Covers:
- Matched check-in
- Unmatched check-in
- Duplicate check-in (same face, same session)
- Inactive session rejection (closed)
- Missing required fields (session_id, embedding, face_image)
"""

import io
import json

import numpy as np
import pytest
from django.test import Client
from django.urls import reverse

from apps.checkin.models import CheckIn
from apps.classes.models import Class
from apps.faces.models import Face, FaceGroup
from apps.sessions.models import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CHECKIN_MATCH_URL = "/api/checkin/match/"


def _make_embedding_bytes(vec: list[float]) -> bytes:
    return np.array(vec, dtype=np.float32).tobytes()


def _unit_vec(dim: int, index: int) -> list[float]:
    v = [0.0] * dim
    v[index] = 1.0
    return v


def _fake_image(name: str = "face.jpg") -> io.BytesIO:
    """Return a minimal JPEG-like byte stream for upload tests."""
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
def active_session(klass):
    return Session.objects.create(klass=klass, name="Active Session")


@pytest.fixture
def closed_session(klass):
    session = Session.objects.create(klass=klass, name="Closed Session")
    session.close()
    return session


@pytest.fixture
def enrolled_face(face_group):
    """A face enrolled with a unit vector along axis 0."""
    return Face.objects.create(
        face_group=face_group,
        name="Alice",
        custom_id="alice-001",
        embedding=_make_embedding_bytes(_unit_vec(128, 0)),
    )


# ---------------------------------------------------------------------------
# Matched check-in
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestMatchedCheckin:
    def test_matched_checkin_returns_200_with_face_info(
        self, client, active_session, enrolled_face
    ):
        query = _unit_vec(128, 0)  # identical to enrolled_face
        response = client.post(
            CHECKIN_MATCH_URL,
            data={
                "session_id": active_session.pk,
                "embedding": json.dumps(query),
                "face_image": _fake_image(),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["matched"] is True
        assert data["face"]["id"] == enrolled_face.pk
        assert data["face"]["name"] == "Alice"
        assert data["face"]["custom_id"] == "alice-001"
        assert "checkin_id" in data

    def test_matched_checkin_creates_checkin_record(
        self, client, active_session, enrolled_face
    ):
        query = _unit_vec(128, 0)
        client.post(
            CHECKIN_MATCH_URL,
            data={
                "session_id": active_session.pk,
                "embedding": json.dumps(query),
                "face_image": _fake_image(),
            },
        )
        assert CheckIn.objects.filter(session=active_session, matched=True).count() == 1

    def test_matched_checkin_includes_top_matches(
        self, client, active_session, enrolled_face
    ):
        query = _unit_vec(128, 0)
        response = client.post(
            CHECKIN_MATCH_URL,
            data={
                "session_id": active_session.pk,
                "embedding": json.dumps(query),
                "face_image": _fake_image(),
            },
        )
        data = response.json()
        assert "top_matches" in data
        assert len(data["top_matches"]) >= 1


# ---------------------------------------------------------------------------
# Unmatched check-in
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUnmatchedCheckin:
    def test_unmatched_checkin_returns_200_with_matched_false(
        self, client, active_session, enrolled_face
    ):
        # Query along axis 1 → orthogonal to enrolled_face (axis 0) → similarity = 0
        query = _unit_vec(128, 1)
        response = client.post(
            CHECKIN_MATCH_URL,
            data={
                "session_id": active_session.pk,
                "embedding": json.dumps(query),
                "face_image": _fake_image(),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["matched"] is False
        assert data["already_checked_in"] is False

    def test_unmatched_checkin_still_creates_checkin_record(
        self, client, active_session, enrolled_face
    ):
        query = _unit_vec(128, 1)
        client.post(
            CHECKIN_MATCH_URL,
            data={
                "session_id": active_session.pk,
                "embedding": json.dumps(query),
                "face_image": _fake_image(),
            },
        )
        assert CheckIn.objects.filter(session=active_session, matched=False).count() == 1


# ---------------------------------------------------------------------------
# Duplicate check-in
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDuplicateCheckin:
    def test_duplicate_checkin_flagged(self, client, active_session, enrolled_face):
        query = _unit_vec(128, 0)
        payload = {
            "session_id": active_session.pk,
            "embedding": json.dumps(query),
        }

        # First check-in
        client.post(CHECKIN_MATCH_URL, data={**payload, "face_image": _fake_image()})
        # Second check-in (duplicate)
        response = client.post(
            CHECKIN_MATCH_URL, data={**payload, "face_image": _fake_image()}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["matched"] is True
        assert data["already_checked_in"] is True

    def test_duplicate_checkin_still_creates_second_record(
        self, client, active_session, enrolled_face
    ):
        """All attempts are logged, even duplicates."""
        query = _unit_vec(128, 0)
        payload = {
            "session_id": active_session.pk,
            "embedding": json.dumps(query),
        }
        client.post(CHECKIN_MATCH_URL, data={**payload, "face_image": _fake_image()})
        client.post(CHECKIN_MATCH_URL, data={**payload, "face_image": _fake_image()})

        assert CheckIn.objects.filter(session=active_session).count() == 2


# ---------------------------------------------------------------------------
# Inactive session rejection
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestInactiveSessionRejection:
    def _post(self, client, session_pk):
        return client.post(
            CHECKIN_MATCH_URL,
            data={
                "session_id": session_pk,
                "embedding": json.dumps(_unit_vec(128, 0)),
                "face_image": _fake_image(),
            },
        )

    def test_closed_session_returns_409(self, client, closed_session):
        response = self._post(client, closed_session.pk)
        assert response.status_code == 409

    def test_nonexistent_session_returns_404(self, client, db):
        response = self._post(client, 999999)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Missing / invalid fields
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestMissingFields:
    def test_missing_session_id_returns_400(self, client, db):
        response = client.post(
            CHECKIN_MATCH_URL,
            data={
                "embedding": json.dumps(_unit_vec(128, 0)),
                "face_image": _fake_image(),
            },
        )
        assert response.status_code == 400
        assert "session_id" in response.json().get("error", "")

    def test_invalid_session_id_returns_400(self, client, db):
        response = client.post(
            CHECKIN_MATCH_URL,
            data={
                "session_id": "not-an-int",
                "embedding": json.dumps(_unit_vec(128, 0)),
                "face_image": _fake_image(),
            },
        )
        assert response.status_code == 400

    def test_missing_embedding_returns_400(self, client, active_session):
        response = client.post(
            CHECKIN_MATCH_URL,
            data={
                "session_id": active_session.pk,
                "face_image": _fake_image(),
            },
        )
        assert response.status_code == 400
        assert "embedding" in response.json().get("error", "")

    def test_invalid_embedding_json_returns_400(self, client, active_session):
        response = client.post(
            CHECKIN_MATCH_URL,
            data={
                "session_id": active_session.pk,
                "embedding": "not-json",
                "face_image": _fake_image(),
            },
        )
        assert response.status_code == 400

    def test_embedding_not_list_returns_400(self, client, active_session):
        response = client.post(
            CHECKIN_MATCH_URL,
            data={
                "session_id": active_session.pk,
                "embedding": json.dumps({"key": "value"}),
                "face_image": _fake_image(),
            },
        )
        assert response.status_code == 400

    def test_missing_face_image_returns_400(self, client, active_session):
        response = client.post(
            CHECKIN_MATCH_URL,
            data={
                "session_id": active_session.pk,
                "embedding": json.dumps(_unit_vec(128, 0)),
            },
        )
        assert response.status_code == 400
        assert "face_image" in response.json().get("error", "")
