from django.db import models

from apps.faces.models import Face
from apps.sessions.models import Session


class CheckIn(models.Model):
    """Records a single check-in attempt (matched or unmatched)."""

    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="checkins",
        verbose_name="คาบเรียน",
    )
    face = models.ForeignKey(
        Face,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkins",
        verbose_name="ใบหน้า",
        help_text="ว่างเปล่าเมื่อไม่พบใบหน้าที่ตรงกัน",
    )
    matched = models.BooleanField(default=False, verbose_name="ตรงกัน")
    checked_in_at = models.DateTimeField(auto_now_add=True, verbose_name="เวลาเช็กอิน")
    raw_face_image = models.ImageField(
        upload_to="checkins/images/",
        verbose_name="ภาพใบหน้า",
        help_text="ภาพใบหน้าที่ถ่ายขณะเช็กอิน เก็บไว้เพื่อตรวจสอบ",
    )

    class Meta:
        ordering = ["-checked_in_at"]
        verbose_name = "การเช็กอิน"
        verbose_name_plural = "การเช็กอิน"

    def __str__(self) -> str:
        status = "matched" if self.matched else "unmatched"
        return f"CheckIn #{self.pk} [{status}] @ {self.checked_in_at}"
