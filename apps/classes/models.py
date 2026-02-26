from django.db import models

from apps.faces.models import FaceGroup


class Class(models.Model):
    """A class that groups multiple sessions and is tied to a face group."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    face_group = models.ForeignKey(
        FaceGroup,
        on_delete=models.PROTECT,
        related_name="classes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Class"
        verbose_name_plural = "Classes"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class ClassTag(models.Model):
    """A tag attached to a class for organisation and filtering."""

    klass = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name="tags",
        db_column="class_id",
    )
    tag = models.CharField(max_length=100)

    class Meta:
        unique_together = [("klass", "tag")]
        ordering = ["tag"]

    def __str__(self) -> str:
        return self.tag
