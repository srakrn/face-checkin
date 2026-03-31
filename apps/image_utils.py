import os
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps


MAX_IMAGE_BYTES = 200 * 1024
MAX_IMAGE_DIMENSION = 1600
JPEG_QUALITIES = (85, 75, 65, 55, 45, 35)
MIN_DIMENSION = 400


def downscale_image_for_storage(uploaded_file, *, max_bytes: int = MAX_IMAGE_BYTES) -> ContentFile:
    """
    Convert an uploaded image to JPEG and shrink it until it fits within
    ``max_bytes``. The returned object can be saved directly to an ImageField.
    """
    uploaded_file.seek(0)
    with Image.open(uploaded_file) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        elif image.mode == "L":
            image = image.convert("RGB")

        image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))

        for attempt in range(6):
            for quality in JPEG_QUALITIES:
                buffer = BytesIO()
                image.save(buffer, format="JPEG", optimize=True, quality=quality)
                if buffer.tell() <= max_bytes:
                    return ContentFile(buffer.getvalue())

            width = max(MIN_DIMENSION, int(image.width * 0.85))
            height = max(MIN_DIMENSION, int(image.height * 0.85))
            if width == image.width and height == image.height:
                break
            image = image.resize((width, height), Image.Resampling.LANCZOS)

        buffer = BytesIO()
        image.save(buffer, format="JPEG", optimize=True, quality=JPEG_QUALITIES[-1])
        return ContentFile(buffer.getvalue())


def jpeg_upload_name(original_name: str) -> str:
    stem, _ = os.path.splitext(original_name or "image")
    return f"{stem or 'image'}.jpg"
