from django.db import models

from apps.faces.models import Face
from apps.sessions.models import Session


class CheckIn(models.Model):
    """Records a single check-in attempt (matched or unmatched)."""

    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="checkins",
    )
    face = models.ForeignKey(
        Face,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkins",
        help_text="Null when the attempt did not match any enrolled face.",
    )
    matched = models.BooleanField(default=False)
    checked_in_at = models.DateTimeField(auto_now_add=True)
    raw_face_image = models.ImageField(
        upload_to="checkins/images/",
        help_text="Raw face image captured at check-in time, stored for audit.",
    )

    class Meta:
        ordering = ["-checked_in_at"]

    def __str__(self) -> str:
        status = "matched" if self.matched else "unmatched"
        return f"CheckIn #{self.pk} [{status}] @ {self.checked_in_at}"
