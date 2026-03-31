import io

import numpy as np
import pytest
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
