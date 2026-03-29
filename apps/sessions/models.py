from django.db import models
from django.utils import timezone

from apps.classes.models import Class


class Session(models.Model):
    """A check-in slot within a class."""

    class State(models.TextChoices):
        ACTIVE = "active", "เปิดให้เช็กอิน"
        CLOSED = "closed", "ปิดไม่ให้เช็กอิน"

    klass = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="sessions",
        db_column="class_id",
        verbose_name="วิชา",
    )
    name = models.CharField(max_length=255, verbose_name="ชื่อคาบเรียน")
    state = models.CharField(
        max_length=10,
        choices=State.choices,
        default=State.ACTIVE,
        verbose_name="สถานะ",
    )
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="เวลาเริ่มต้น",
        help_text="เวลาเริ่มต้นที่กำหนด (ข้อมูลอ้างอิง)",
    )
    auto_close_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="ปิดอัตโนมัติเมื่อ",
        help_text="หากกำหนดไว้ คาบเรียนจะปิดโดยอัตโนมัติเมื่อถึงเวลานี้",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="สร้างเมื่อ")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="แก้ไขล่าสุด")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "คาบเรียน"
        verbose_name_plural = "คาบเรียน"

    def __str__(self) -> str:
        return f"{self.name} [{self.state}]"

    # ------------------------------------------------------------------
    # State transition helpers
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Transition Closed → Active."""
        if self.state != self.State.CLOSED:
            raise ValueError(f"Cannot open a session in state '{self.state}'.")
        self.state = self.State.ACTIVE
        self.save(update_fields=["state", "updated_at"])

    def close(self) -> None:
        """Transition Active → Closed."""
        if self.state != self.State.ACTIVE:
            raise ValueError(f"Cannot close a session in state '{self.state}'.")
        self.state = self.State.CLOSED
        self.save(update_fields=["state", "updated_at"])

    @property
    def should_auto_open(self) -> bool:
        """Return True if the session should be auto-opened right now.

        Only reopen sessions whose scheduled time has arrived and whose
        auto-close time has not already passed.
        """
        return (
            self.state == self.State.CLOSED
            and self.scheduled_at is not None
            and timezone.now() >= self.scheduled_at
            and (
                self.auto_close_at is None
                or timezone.now() < self.auto_close_at
            )
        )

    @property
    def should_auto_close(self) -> bool:
        """Return True if the session should be auto-closed right now."""
        return (
            self.state == self.State.ACTIVE
            and self.auto_close_at is not None
            and timezone.now() >= self.auto_close_at
        )
