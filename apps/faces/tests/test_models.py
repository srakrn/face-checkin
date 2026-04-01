import io

import numpy as np
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.faces.models import Face, FaceGroup


def _large_image(name: str = "face.png") -> io.BytesIO:
    rng = np.random.default_rng(4321)
    pixels = rng.integers(0, 256, size=(2200, 2200, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(pixels).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@pytest.mark.django_db
def test_face_photo_is_downscaled_below_200kb():
    face_group = FaceGroup.objects.create(name="Test Group")
    face = Face.objects.create(
        face_group=face_group,
        name="Alice",
        custom_id="alice-001",
        photo=_large_image(),
    )

    assert face.photo.size < 200 * 1024
    assert face.photo.name.endswith(".jpg")


@pytest.mark.django_db
def test_face_group_accessible_to_owner_and_shared_user():
    user_model = get_user_model()
    owner = user_model.objects.create_user(username="owner", password="password123")
    shared = user_model.objects.create_user(username="shared", password="password123")
    outsider = user_model.objects.create_user(username="outsider", password="password123")

    face_group = FaceGroup.objects.create(name="Owned Group", owner=owner)
    face_group.shared_with_users.add(shared)

    assert list(FaceGroup.objects.accessible_to(owner)) == [face_group]
    assert list(FaceGroup.objects.accessible_to(shared)) == [face_group]
    assert list(FaceGroup.objects.accessible_to(outsider)) == []
    assert face_group.user_has_access(owner) is True
    assert face_group.user_has_access(shared) is True
    assert face_group.user_has_access(outsider) is False
