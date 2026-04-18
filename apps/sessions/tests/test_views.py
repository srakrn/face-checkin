"""
Integration tests for session API views (apps/sessions/views.py).

Covers:
- session_detail: returns correct JSON for existing session, 404 for missing
- session_report: lists all check-ins with correct fields
"""

import io
from datetime import timedelta

import numpy as np
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import override
from PIL import Image

from apps.checkin.models import CheckIn
from apps.classes.models import Course
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
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color="blue").save(buf, format="JPEG")
    buf.name = name
    buf.seek(0)
    return buf


def _create_checkin(session, *, face=None, matched=False, ip_address=None, user_agent=""):
    checkin = CheckIn(
        session=session,
        face=face,
        matched=matched,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    checkin.raw_face_image.save("test.jpg", _fake_image(), save=False)
    checkin.save()
    return checkin


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
def shared_user(db):
    return get_user_model().objects.create_user(
        username="shared",
        password="password123",
        is_staff=True,
    )


@pytest.fixture
def outsider_user(db):
    return get_user_model().objects.create_user(
        username="outsider",
        password="password123",
        is_staff=True,
    )


@pytest.fixture
def face_group(db):
    return FaceGroup.objects.create(name="Test Group")


@pytest.fixture
def owned_face_group(face_group, staff_user):
    face_group.owner = staff_user
    face_group.save(update_fields=["owner"])
    return face_group


@pytest.fixture
def course(owned_face_group, staff_user):
    return Course.objects.create(
        name="Test Course",
        shorthand="TST",
        face_group=owned_face_group,
        owner=staff_user,
    )


@pytest.fixture
def draft_session(course):
    return Session.objects.create(course=course, name="Draft Session")


@pytest.fixture
def active_session(course):
    return Session.objects.create(course=course, name="Active Session")


@pytest.fixture
def closed_session(active_session):
    active_session.close()
    return active_session


@pytest.fixture
def enrolled_face(owned_face_group):
    return Face.objects.create(
        face_group=owned_face_group,
        name="Alice",
        custom_id="alice-001",
        embedding=_make_embedding_bytes(_unit_vec(128, 0)),
    )


@pytest.fixture
def second_enrolled_face(owned_face_group):
    return Face.objects.create(
        face_group=owned_face_group,
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

    def test_returns_correct_course_id(self, auth_client, draft_session, course):
        response = auth_client.get(f"/api/sessions/{draft_session.pk}/")
        data = response.json()
        assert data["course_id"] == course.pk

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
class TestSessionObjectAccess:
    def test_owner_can_access_session_detail(self, auth_client, active_session):
        response = auth_client.get(f"/api/sessions/{active_session.pk}/")
        assert response.status_code == 200

    def test_shared_user_can_access_session_detail(self, shared_user, active_session):
        active_session.course.shared_with_users.add(shared_user)
        client = Client()
        client.force_login(shared_user)

        response = client.get(f"/api/sessions/{active_session.pk}/")

        assert response.status_code == 200

    def test_unshared_user_cannot_access_session_detail(self, outsider_user, active_session):
        client = Client()
        client.force_login(outsider_user)

        response = client.get(f"/api/sessions/{active_session.pk}/")

        assert response.status_code == 404

    def test_shared_user_can_access_report_page(self, shared_user, active_session):
        active_session.course.shared_with_users.add(shared_user)
        client = Client()
        client.force_login(shared_user)

        response = client.get(f"/sessions/{active_session.pk}/report/")

        assert response.status_code == 200

    def test_unshared_user_cannot_access_checkin_image(self, outsider_user, checkin_matched):
        client = Client()
        client.force_login(outsider_user)

        response = client.get(f"/sessions/checkins/{checkin_matched.pk}/image/")

        assert response.status_code == 404


@pytest.mark.django_db
class TestCustomLoginFlow:
    def test_index_hides_active_sessions_when_logged_out(self, client, active_session):
        response = client.get("/")

        content = response.content.decode()
        assert response.status_code == 200
        assert "เข้าสู่ระบบ" in content
        assert active_session.name not in content
        assert "schimudtcheck-logo.svg" in content
        assert "<nav" not in content

    def test_index_shows_active_sessions_when_logged_in(self, client, staff_user, active_session):
        client.force_login(staff_user)

        response = client.get("/")

        content = response.content.decode()
        assert response.status_code == 200
        assert active_session.name in content
        assert "Admin" in content
        assert "ออกจากระบบ" in content

    def test_index_hides_inaccessible_sessions_from_logged_in_user(
        self, client, outsider_user, active_session
    ):
        client.force_login(outsider_user)

        response = client.get("/")

        content = response.content.decode()
        assert response.status_code == 200
        assert active_session.name not in content

    def test_login_page_renders(self, client):
        response = client.get("/login/")

        content = response.content.decode()
        assert response.status_code == 200
        assert "เข้าสู่ระบบเพื่อเข้าถึงหน้าจัดการและรายการคาบเรียนที่เปิดอยู่" in content
        assert 'name="username"' in content
        assert 'name="password"' in content


@pytest.mark.django_db
class TestSessionStateMutationViews:
    def test_course_session_list_renders_open_button_for_closed_session(
        self, client, staff_user, course, closed_session
    ):
        client.force_login(staff_user)

        response = client.get(f"/courses/{course.pk}/sessions/")

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
            "/login/?next=/courses/",
            {"username": "staff", "password": "password123"},
        )

        assert response.status_code == 302
        assert response["Location"] == "/courses/"


@pytest.mark.django_db
class TestSessionManagementFilters:
    def test_session_list_search_filters_by_partial_name(self, client, staff_user, course):
        client.force_login(staff_user)
        target = Session.objects.create(course=course, name="Physics Lab")
        Session.objects.create(course=course, name="Chemistry Review")

        response = client.get(f"/courses/{course.pk}/sessions/", {"q": "phys"})

        sessions = list(response.context["sessions"])
        assert response.status_code == 200
        assert sessions == [target]

    def test_session_list_filters_by_active_status(self, client, staff_user, course):
        client.force_login(staff_user)
        active = Session.objects.create(course=course, name="Open Session")
        closed = Session.objects.create(course=course, name="Closed Session")
        closed.close()

        response = client.get(f"/courses/{course.pk}/sessions/", {"state": "active"})

        sessions = list(response.context["sessions"])
        assert response.status_code == 200
        assert active in sessions
        assert closed not in sessions

    def test_session_list_filters_by_closed_status(self, client, staff_user, course):
        client.force_login(staff_user)
        active = Session.objects.create(course=course, name="Open Session")
        closed = Session.objects.create(course=course, name="Closed Session")
        closed.close()

        response = client.get(f"/courses/{course.pk}/sessions/", {"state": "closed"})

        sessions = list(response.context["sessions"])
        assert response.status_code == 200
        assert closed in sessions
        assert active not in sessions

    def test_session_list_can_sort_by_name(self, client, staff_user, course):
        client.force_login(staff_user)
        session_b = Session.objects.create(course=course, name="Beta Session")
        session_a = Session.objects.create(course=course, name="Alpha Session")

        response = client.get(f"/courses/{course.pk}/sessions/", {"sort": "name_asc"})

        sessions = list(response.context["sessions"][:2])
        assert response.status_code == 200
        assert sessions == [session_a, session_b]

    def test_session_list_can_sort_by_scheduled_at(self, client, staff_user, course):
        client.force_login(staff_user)
        later = Session.objects.create(
            course=course,
            name="Later Session",
            scheduled_at=timezone.now() + timedelta(days=1),
        )
        earlier = Session.objects.create(
            course=course,
            name="Earlier Session",
            scheduled_at=timezone.now() - timedelta(days=1),
        )

        response = client.get(f"/courses/{course.pk}/sessions/", {"sort": "scheduled_asc"})

        sessions = list(response.context["sessions"][:2])
        assert response.status_code == 200
        assert sessions == [earlier, later]

    def test_report_search_filters_by_participant_name(
        self, client, staff_user, active_session, enrolled_face, second_enrolled_face
    ):
        client.force_login(staff_user)
        alpha = _create_checkin(active_session, face=enrolled_face, matched=True)
        beta = _create_checkin(active_session, face=second_enrolled_face, matched=True)

        response = client.get(f"/sessions/{active_session.pk}/report/", {"q": "ali"})

        checkins = list(response.context["checkins"])
        assert response.status_code == 200
        assert checkins == [alpha]
        assert beta not in checkins

    def test_report_search_filters_by_custom_id(
        self, client, staff_user, active_session, enrolled_face, second_enrolled_face
    ):
        client.force_login(staff_user)
        alpha = _create_checkin(active_session, face=enrolled_face, matched=True)
        _create_checkin(active_session, face=second_enrolled_face, matched=True)

        response = client.get(f"/sessions/{active_session.pk}/report/", {"q": "alice-001"})

        checkins = list(response.context["checkins"])
        assert response.status_code == 200
        assert checkins == [alpha]

    def test_report_filters_by_matched_status(
        self, client, staff_user, active_session, enrolled_face, checkin_unmatched
    ):
        client.force_login(staff_user)
        matched = _create_checkin(active_session, face=enrolled_face, matched=True)

        response = client.get(f"/sessions/{active_session.pk}/report/", {"matched": "matched"})

        checkins = list(response.context["checkins"])
        assert response.status_code == 200
        assert checkins == [matched]
        assert checkin_unmatched not in checkins

    def test_report_filters_by_unmatched_status(
        self, client, staff_user, active_session, enrolled_face, checkin_unmatched
    ):
        client.force_login(staff_user)
        _create_checkin(active_session, face=enrolled_face, matched=True)

        response = client.get(f"/sessions/{active_session.pk}/report/", {"matched": "unmatched"})

        checkins = list(response.context["checkins"])
        assert response.status_code == 200
        assert checkins == [checkin_unmatched]

    def test_report_filters_by_suspicious_only(
        self, client, staff_user, active_session, enrolled_face, second_enrolled_face
    ):
        client.force_login(staff_user)
        normal = _create_checkin(
            active_session,
            face=enrolled_face,
            matched=True,
            ip_address="10.0.0.1",
            user_agent="kiosk-browser",
        )
        _create_checkin(
            active_session,
            face=second_enrolled_face,
            matched=True,
            ip_address="10.0.0.1",
            user_agent="kiosk-browser",
        )
        suspicious = _create_checkin(
            active_session,
            face=None,
            matched=False,
            ip_address="10.0.0.2",
            user_agent="rogue-browser",
        )

        response = client.get(f"/sessions/{active_session.pk}/report/", {"anomaly": "suspicious_only"})

        checkins = list(response.context["checkins"])
        assert response.status_code == 200
        assert suspicious in checkins
        assert normal not in checkins

    def test_report_filters_by_normal_only(
        self, client, staff_user, active_session, enrolled_face, second_enrolled_face
    ):
        client.force_login(staff_user)
        normal = _create_checkin(
            active_session,
            face=enrolled_face,
            matched=True,
            ip_address="10.0.0.1",
            user_agent="kiosk-browser",
        )
        _create_checkin(
            active_session,
            face=second_enrolled_face,
            matched=True,
            ip_address="10.0.0.1",
            user_agent="kiosk-browser",
        )
        _create_checkin(
            active_session,
            face=None,
            matched=False,
            ip_address="10.0.0.2",
            user_agent="rogue-browser",
        )

        response = client.get(f"/sessions/{active_session.pk}/report/", {"anomaly": "normal_only"})

        checkins = list(response.context["checkins"])
        assert response.status_code == 200
        assert normal in checkins
        assert all(not checkin.anomaly_reasons for checkin in checkins)

    def test_report_can_sort_by_time_desc(
        self, client, staff_user, active_session, enrolled_face, second_enrolled_face
    ):
        client.force_login(staff_user)
        first = _create_checkin(active_session, face=enrolled_face, matched=True)
        second = _create_checkin(active_session, face=second_enrolled_face, matched=True)
        CheckIn.objects.filter(pk=first.pk).update(checked_in_at=timezone.now() - timedelta(hours=1))
        CheckIn.objects.filter(pk=second.pk).update(checked_in_at=timezone.now())
        first.refresh_from_db()
        second.refresh_from_db()

        response = client.get(f"/sessions/{active_session.pk}/report/", {"sort": "time_desc"})

        checkins = list(response.context["checkins"][:2])
        assert response.status_code == 200
        assert checkins == [second, first]

    def test_report_can_sort_by_name_asc(
        self, client, staff_user, active_session, enrolled_face, second_enrolled_face
    ):
        client.force_login(staff_user)
        beta = _create_checkin(active_session, face=second_enrolled_face, matched=True)
        alpha = _create_checkin(active_session, face=enrolled_face, matched=True)

        response = client.get(f"/sessions/{active_session.pk}/report/", {"sort": "name_asc"})

        checkins = list(response.context["checkins"][:2])
        assert response.status_code == 200
        assert checkins == [alpha, beta]

    def test_report_unique_mode_combines_with_search_filters(
        self, client, staff_user, active_session, enrolled_face, second_enrolled_face
    ):
        client.force_login(staff_user)
        first = _create_checkin(active_session, face=enrolled_face, matched=True)
        second = _create_checkin(active_session, face=enrolled_face, matched=True)
        other = _create_checkin(active_session, face=second_enrolled_face, matched=True)
        CheckIn.objects.filter(pk=first.pk).update(checked_in_at=timezone.now() - timedelta(hours=2))
        CheckIn.objects.filter(pk=second.pk).update(checked_in_at=timezone.now() - timedelta(hours=1))
        first.refresh_from_db()
        second.refresh_from_db()
        other.refresh_from_db()

        response = client.get(
            f"/sessions/{active_session.pk}/report/",
            {"unique": "1", "q": "alice", "sort": "time_desc"},
        )

        checkins = list(response.context["checkins"])
        assert response.status_code == 200
        assert checkins == [first]
        assert second not in checkins
        assert other not in checkins

    def test_report_renders_inline_custom_id_without_separate_column(
        self, client, staff_user, active_session, enrolled_face
    ):
        client.force_login(staff_user)
        _create_checkin(active_session, face=enrolled_face, matched=True)

        response = client.get(f"/sessions/{active_session.pk}/report/")

        content = response.content.decode()
        assert response.status_code == 200
        assert "Alice (<code>alice-001</code>)" in content
        assert "<th>Custom ID</th>" not in content

    def test_report_links_preserve_unique_filter_state(
        self, client, staff_user, active_session, enrolled_face
    ):
        client.force_login(staff_user)
        _create_checkin(active_session, face=enrolled_face, matched=True)

        response = client.get(
            f"/sessions/{active_session.pk}/report/",
            {"unique": "1", "q": "alice", "matched": "matched", "sort": "name_asc"},
        )

        content = response.content.decode()
        assert response.status_code == 200
        assert f'{reverse("sessions:report_csv", args=[active_session.pk])}?unique=1&amp;q=alice&amp;matched=matched&amp;sort=name_asc' in content
        assert f'{reverse("sessions:report_page", args=[active_session.pk])}?q=alice&amp;matched=matched&amp;sort=name_asc' in content
        assert 'name="unique" value="1"' in content

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
        response = client.get("/courses/")

        assert response.status_code == 302
        assert response["Location"] == "/login/?next=/courses/"

    def test_unshared_user_cannot_list_owner_class_sessions(
        self, client, outsider_user, course
    ):
        client.force_login(outsider_user)

        response = client.get(f"/courses/{course.pk}/sessions/")

        assert response.status_code == 404

    def test_shared_user_can_list_shared_class_sessions(
        self, client, shared_user, course
    ):
        course.shared_with_users.add(shared_user)
        client.force_login(shared_user)

        response = client.get(f"/courses/{course.pk}/sessions/")

        assert response.status_code == 200


@pytest.mark.django_db
class TestUserBootstrapPermissions:
    def test_new_user_gets_staff_access_and_project_permissions(self):
        user = get_user_model().objects.create_user(
            username="autheditor",
            password="password123",
        )
        user.refresh_from_db()

        assert user.is_staff is True
        assert user.has_perm("faces.view_facegroup")
        assert user.has_perm("classes.add_course")
        assert user.has_perm("checkin_sessions.change_session")
        assert user.has_perm("checkin.view_checkin")


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
