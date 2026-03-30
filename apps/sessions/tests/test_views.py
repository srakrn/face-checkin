"""
Integration tests for session API views (apps/sessions/views.py).

Covers:
- session_detail: returns correct JSON for existing session, 404 for missing
- session_report: lists all check-ins with correct fields
"""

import io

import numpy as np
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.template.loader import render_to_string
from django.utils.translation import override

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
def auth_client(client, staff_user):
    client.force_login(staff_user)
    return client


@pytest.fixture
def staff_user(db):
    return get_user_model().objects.create_user(
        username="staff",
        password="password123",
        is_staff=True,
    )


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
def closed_session(active_session):
    active_session.close()
    return active_session


@pytest.fixture
def enrolled_face(face_group):
    return Face.objects.create(
        face_group=face_group,
        name="Alice",
        custom_id="alice-001",
        embedding=_make_embedding_bytes(_unit_vec(128, 0)),
    )


@pytest.fixture
def second_enrolled_face(face_group):
    return Face.objects.create(
        face_group=face_group,
        name="Bob",
        custom_id="bob-002",
        embedding=_make_embedding_bytes(_unit_vec(128, 1)),
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
    def test_returns_200_for_existing_session(self, auth_client, draft_session):
        response = auth_client.get(f"/api/sessions/{draft_session.pk}/")
        assert response.status_code == 200

    def test_returns_correct_id(self, auth_client, draft_session):
        response = auth_client.get(f"/api/sessions/{draft_session.pk}/")
        data = response.json()
        assert data["id"] == draft_session.pk

    def test_returns_correct_name(self, auth_client, draft_session):
        response = auth_client.get(f"/api/sessions/{draft_session.pk}/")
        data = response.json()
        assert data["name"] == "Draft Session"

    def test_returns_correct_state_active(self, auth_client, active_session):
        response = auth_client.get(f"/api/sessions/{active_session.pk}/")
        data = response.json()
        assert data["state"] == "active"

    def test_returns_correct_class_id(self, auth_client, draft_session, klass):
        response = auth_client.get(f"/api/sessions/{draft_session.pk}/")
        data = response.json()
        assert data["class_id"] == klass.pk

    def test_scheduled_at_none_when_not_set(self, auth_client, draft_session):
        response = auth_client.get(f"/api/sessions/{draft_session.pk}/")
        data = response.json()
        assert data["scheduled_at"] is None

    def test_auto_close_at_none_when_not_set(self, auth_client, draft_session):
        response = auth_client.get(f"/api/sessions/{draft_session.pk}/")
        data = response.json()
        assert data["auto_close_at"] is None

    def test_returns_404_for_nonexistent_session(self, auth_client, db):
        response = auth_client.get("/api/sessions/999999/")
        assert response.status_code == 404

    def test_post_method_not_allowed(self, auth_client, draft_session):
        response = auth_client.post(f"/api/sessions/{draft_session.pk}/")
        assert response.status_code == 405


# ---------------------------------------------------------------------------
# GET /api/sessions/<pk>/report/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSessionReport:
    def test_returns_200_for_existing_session(self, auth_client, active_session):
        response = auth_client.get(f"/api/sessions/{active_session.pk}/report/")
        assert response.status_code == 200

    def test_returns_correct_session_id(self, auth_client, active_session):
        response = auth_client.get(f"/api/sessions/{active_session.pk}/report/")
        data = response.json()
        assert data["session_id"] == active_session.pk

    def test_empty_checkins_list_when_no_checkins(self, auth_client, active_session):
        response = auth_client.get(f"/api/sessions/{active_session.pk}/report/")
        data = response.json()
        assert data["checkins"] == []

    def test_lists_all_checkins(
        self, auth_client, active_session, checkin_matched, checkin_unmatched
    ):
        response = auth_client.get(f"/api/sessions/{active_session.pk}/report/")
        data = response.json()
        assert len(data["checkins"]) == 2

    def test_matched_checkin_has_correct_fields(
        self, auth_client, active_session, checkin_matched, enrolled_face
    ):
        response = auth_client.get(f"/api/sessions/{active_session.pk}/report/")
        data = response.json()
        matched = next(c for c in data["checkins"] if c["matched"])
        assert matched["face_id"] == enrolled_face.pk
        assert matched["face_name"] == "Alice"
        assert matched["face_custom_id"] == "alice-001"
        assert "checked_in_at" in matched

    def test_unmatched_checkin_has_null_face_fields(
        self, auth_client, active_session, checkin_unmatched
    ):
        response = auth_client.get(f"/api/sessions/{active_session.pk}/report/")
        data = response.json()
        unmatched = next(c for c in data["checkins"] if not c["matched"])
        assert unmatched["face_id"] is None
        assert unmatched["face_name"] is None
        assert unmatched["face_custom_id"] is None

    def test_returns_404_for_nonexistent_session(self, auth_client, db):
        response = auth_client.get("/api/sessions/999999/report/")
        assert response.status_code == 404

    def test_post_method_not_allowed(self, auth_client, active_session):
        response = auth_client.post(f"/api/sessions/{active_session.pk}/report/")
        assert response.status_code == 405


@pytest.mark.django_db
class TestSessionApiAuth:
    def test_detail_redirects_anonymous_user_to_login(self, client, active_session):
        response = client.get(f"/api/sessions/{active_session.pk}/")

        assert response.status_code == 302
        assert response["Location"] == f"/login/?next=/api/sessions/{active_session.pk}/"

    def test_report_redirects_anonymous_user_to_login(self, client, active_session):
        response = client.get(f"/api/sessions/{active_session.pk}/report/")

        assert response.status_code == 302
        assert response["Location"] == f"/login/?next=/api/sessions/{active_session.pk}/report/"


@pytest.mark.django_db
class TestCustomLoginFlow:
    def test_index_hides_active_sessions_when_logged_out(self, client, active_session):
        response = client.get("/")

        content = response.content.decode()
        assert response.status_code == 200
        assert "เข้าสู่ระบบ" in content
        assert active_session.name not in content
        assert "เข้าสู่ระบบเพื่อดูรายการคาบเรียนที่เปิดให้เช็กอิน" in content

    def test_index_shows_active_sessions_when_logged_in(self, client, staff_user, active_session):
        client.force_login(staff_user)

        response = client.get("/")

        content = response.content.decode()
        assert response.status_code == 200
        assert active_session.name in content
        assert "Admin" in content
        assert "ออกจากระบบ" in content

    def test_login_page_renders(self, client):
        response = client.get("/login/")

        content = response.content.decode()
        assert response.status_code == 200
        assert "เข้าสู่ระบบเพื่อเข้าถึงหน้าจัดการและรายการคาบเรียนที่เปิดอยู่" in content
        assert 'name="username"' in content
        assert 'name="password"' in content


@pytest.mark.django_db
class TestSessionStateMutationViews:
    def test_class_session_list_renders_open_button_for_closed_session(
        self, client, staff_user, klass, closed_session
    ):
        client.force_login(staff_user)

        response = client.get(f"/sessions/classes/{klass.pk}/")

        content = response.content.decode()
        assert response.status_code == 200
        assert "เปิดการเช็กอิน" in content

    def test_open_closed_session_returns_updated_row(self, client, staff_user, closed_session):
        client.force_login(staff_user)

        response = client.post(f"/sessions/{closed_session.pk}/open/")

        closed_session.refresh_from_db()
        content = response.content.decode()
        assert response.status_code == 200
        assert closed_session.state == Session.State.ACTIVE
        assert "ปิดการเช็กอิน" in content

    def test_close_active_session_returns_updated_row(self, client, staff_user, active_session):
        client.force_login(staff_user)

        response = client.post(f"/sessions/{active_session.pk}/close/")

        active_session.refresh_from_db()
        content = response.content.decode()
        assert response.status_code == 200
        assert active_session.state == Session.State.CLOSED
        assert "เปิดการเช็กอิน" in content

    def test_login_redirects_to_next_url_when_credentials_are_valid(self, client, staff_user):
        response = client.post(
            "/login/?next=/sessions/",
            {"username": "staff", "password": "password123"},
        )

        assert response.status_code == 302
        assert response["Location"] == "/sessions/"

    def test_login_shows_error_for_invalid_credentials(self, client):
        response = client.post(
            "/login/",
            {"username": "wrong", "password": "bad-password"},
        )

        content = response.content.decode()
        assert response.status_code == 200
        assert "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง" in content

    def test_logout_clears_authenticated_session(self, client, staff_user):
        client.force_login(staff_user)

        response = client.post("/logout/", follow=True)

        content = response.content.decode()
        assert response.status_code == 200
        assert "_auth_user_id" not in client.session
        assert "ออกจากระบบแล้ว" in content
        assert "เข้าสู่ระบบ" in content

    def test_session_pages_redirect_to_custom_login(self, client):
        response = client.get("/sessions/")

        assert response.status_code == 302
        assert response["Location"] == "/login/?next=/sessions/"


@pytest.mark.django_db
class TestSessionReportPage:
    def test_renders_thai_translations_and_face_image(
        self, client, staff_user, active_session, checkin_matched
    ):
        client.force_login(staff_user)

        with override("th"):
            response = client.get(f"/sessions/{active_session.pk}/report/")

        content = response.content.decode()
        assert response.status_code == 200
        assert "รายงาน" in content
        assert "ประวัติการเช็กอิน" in content
        assert f'/sessions/checkins/{checkin_matched.pk}/image/' in content
        assert 'alt="ภาพใบหน้าสำหรับการเช็กอิน #' in content

    def test_renders_remap_and_delete_controls(
        self, client, staff_user, active_session, checkin_matched, second_enrolled_face
    ):
        client.force_login(staff_user)

        response = client.get(f"/sessions/{active_session.pk}/report/")

        content = response.content.decode()
        assert response.status_code == 200
        assert f'/sessions/checkins/{checkin_matched.pk}/remap/' in content
        assert f'/sessions/checkins/{checkin_matched.pk}/delete/' in content
        assert "Bob (bob-002)" in content

    def test_checkin_image_requires_login(self, client, checkin_matched):
        response = client.get(f"/sessions/checkins/{checkin_matched.pk}/image/")
        assert response.status_code == 302
        assert "login" in response["Location"]

    def test_checkin_image_streams_for_authenticated_user(
        self, client, staff_user, checkin_matched
    ):
        client.force_login(staff_user)
        response = client.get(f"/sessions/checkins/{checkin_matched.pk}/image/")

        assert response.status_code == 200
        assert response["Content-Type"] == "image/jpeg"


@pytest.mark.django_db
class TestSessionReportActions:
    def test_checkin_remap_requires_login(self, client, checkin_matched, second_enrolled_face):
        response = client.post(
            f"/sessions/checkins/{checkin_matched.pk}/remap/",
            {"face_id": second_enrolled_face.pk},
        )

        assert response.status_code == 302
        assert "login" in response["Location"]

    def test_checkin_remaps_to_face_in_same_group(
        self, client, staff_user, checkin_matched, second_enrolled_face
    ):
        client.force_login(staff_user)

        response = client.post(
            f"/sessions/checkins/{checkin_matched.pk}/remap/",
            {"face_id": second_enrolled_face.pk},
        )

        checkin_matched.refresh_from_db()
        assert response.status_code == 302
        assert checkin_matched.face == second_enrolled_face
        assert checkin_matched.matched is True

    def test_checkin_remap_preserves_unique_filter(
        self, client, staff_user, checkin_matched, second_enrolled_face
    ):
        client.force_login(staff_user)

        response = client.post(
            f"/sessions/checkins/{checkin_matched.pk}/remap/",
            {"face_id": second_enrolled_face.pk, "unique": "1"},
        )

        assert response.status_code == 302
        assert response["Location"].endswith(f"/sessions/{checkin_matched.session_id}/report/?unique=1")

    def test_checkin_remap_rejects_face_from_another_group(
        self, client, staff_user, checkin_matched, db
    ):
        client.force_login(staff_user)
        other_group = FaceGroup.objects.create(name="Other Group")
        outsider = Face.objects.create(
            face_group=other_group,
            name="Mallory",
            custom_id="mallory-003",
            embedding=_make_embedding_bytes(_unit_vec(128, 2)),
        )

        response = client.post(
            f"/sessions/checkins/{checkin_matched.pk}/remap/",
            {"face_id": outsider.pk},
        )

        checkin_matched.refresh_from_db()
        assert response.status_code == 404
        assert checkin_matched.face.name == "Alice"

    def test_checkin_delete_requires_login(self, client, checkin_matched):
        response = client.post(f"/sessions/checkins/{checkin_matched.pk}/delete/")

        assert response.status_code == 302
        assert "login" in response["Location"]

    def test_checkin_delete_removes_checkin(self, client, staff_user, checkin_matched):
        client.force_login(staff_user)

        response = client.post(f"/sessions/checkins/{checkin_matched.pk}/delete/")

        assert response.status_code == 302
        assert not CheckIn.objects.filter(pk=checkin_matched.pk).exists()

    def test_checkin_delete_preserves_unique_filter(self, client, staff_user, checkin_matched):
        client.force_login(staff_user)

        response = client.post(
            f"/sessions/checkins/{checkin_matched.pk}/delete/",
            {"unique": "1"},
        )

        assert response.status_code == 302
        assert response["Location"].endswith(f"/sessions/{checkin_matched.session_id}/report/?unique=1")


class TestErrorTemplates:
    def test_404_template_renders_thai_copy(self):
        with override("th"):
            content = render_to_string("404.html")

        assert "ไม่พบหน้าที่ต้องการ" in content
        assert "หน้าที่คุณกำลังมองหาไม่มีอยู่" in content
        assert "กลับหน้าหลัก" in content

    def test_403_template_renders_thai_copy(self):
        with override("th"):
            content = render_to_string("403.html")

        assert "ไม่มีสิทธิ์เข้าถึง" in content
        assert "คุณไม่มีสิทธิ์เข้าถึงหน้านี้" in content
        assert "กลับหน้าหลัก" in content
