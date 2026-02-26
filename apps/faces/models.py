import uuid

from django.db import models


class FaceGroup(models.Model):
    """A named collection of enrolled faces (participants)."""

    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class Face(models.Model):
    """An enrolled participant face within a FaceGroup."""

    face_group = models.ForeignKey(
        FaceGroup,
        on_delete=models.CASCADE,
        related_name="faces",
    )
    # custom_id is unique within a face group (not globally)
    custom_id = models.CharField(
        max_length=255,
        default=uuid.uuid4,
        help_text="Unique identifier within the face group. Defaults to a UUID.",
    )
    name = models.CharField(max_length=255)
    remarks = models.TextField(blank=True)
    # Embedding stored as raw bytes (numpy array serialised via numpy.tobytes / frombuffer)
    embedding = models.BinaryField(
        blank=True,
        null=True,
        help_text="128-d face embedding vector stored as raw float32 bytes.",
    )
    photo = models.ImageField(
        upload_to="faces/photos/",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # custom_id must be unique within a face group
        unique_together = [("face_group", "custom_id")]
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.custom_id})"
