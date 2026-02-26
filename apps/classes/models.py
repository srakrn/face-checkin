from django.db import models

from apps.faces.models import FaceGroup


class Class(models.Model):
    """A class that groups multiple sessions and is tied to a face group."""

    name = models.CharField(max_length=255, verbose_name="ชื่อวิชา")
    description = models.TextField(blank=True, verbose_name="คำอธิบาย")
    face_group = models.ForeignKey(
        FaceGroup,
        on_delete=models.PROTECT,
        related_name="classes",
        verbose_name="กลุ่มใบหน้า",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="สร้างเมื่อ")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="แก้ไขล่าสุด")

    class Meta:
        verbose_name = "วิชา"
        verbose_name_plural = "วิชา"
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
        verbose_name="วิชา",
    )
    tag = models.CharField(max_length=100, verbose_name="แท็ก")

    class Meta:
        unique_together = [("klass", "tag")]
        ordering = ["tag"]
        verbose_name = "แท็กวิชา"
        verbose_name_plural = "แท็กวิชา"

    def __str__(self) -> str:
        return self.tag
