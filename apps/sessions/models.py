from django.db import models
from django.utils import timezone

from apps.classes.models import Class


class Session(models.Model):
    """A check-in slot within a class."""

    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"

    klass = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="sessions",
        db_column="class_id",
    )
    name = models.CharField(max_length=255)
    state = models.CharField(
        max_length=10,
        choices=State.choices,
        default=State.DRAFT,
    )
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional scheduled start time (informational).",
    )
    auto_close_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="If set, the session will automatically close at this time.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} [{self.state}]"

    # ------------------------------------------------------------------
    # State transition helpers
    # ------------------------------------------------------------------

    def activate(self) -> None:
        """Transition Draft → Active."""
        if self.state != self.State.DRAFT:
            raise ValueError(f"Cannot activate a session in state '{self.state}'.")
        self.state = self.State.ACTIVE
        self.save(update_fields=["state", "updated_at"])

    def close(self) -> None:
        """Transition Active → Closed."""
        if self.state != self.State.ACTIVE:
            raise ValueError(f"Cannot close a session in state '{self.state}'.")
        self.state = self.State.CLOSED
        self.save(update_fields=["state", "updated_at"])

    @property
    def should_auto_close(self) -> bool:
        """Return True if the session should be auto-closed right now."""
        return (
            self.state == self.State.ACTIVE
            and self.auto_close_at is not None
            and timezone.now() >= self.auto_close_at
        )
