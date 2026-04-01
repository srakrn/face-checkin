from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.faces.models import FaceGroup


class CourseQuerySet(models.QuerySet):
    def accessible_to(self, user):
        if user.is_superuser:
            return self
        if not user.is_authenticated:
            return self.none()
        return self.filter(Q(owner=user) | Q(shared_with_users=user)).distinct()


class Course(models.Model):
    """A course that groups multiple sessions and is tied to a face group."""

    name = models.CharField(max_length=255, verbose_name="ชื่อวิชา")
    shorthand = models.CharField(max_length=50, unique=True, verbose_name="ชื่อย่อ")
    description = models.TextField(blank=True, verbose_name="คำอธิบาย")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_courses",
        verbose_name="เจ้าของ",
    )
    shared_with_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="shared_courses",
        verbose_name="แชร์กับผู้ใช้",
    )
    face_group = models.ForeignKey(
        FaceGroup,
        on_delete=models.PROTECT,
        related_name="courses",
        verbose_name="กลุ่มใบหน้า",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="สร้างเมื่อ")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="แก้ไขล่าสุด")

    objects = CourseQuerySet.as_manager()

    class Meta:
        verbose_name = "วิชา"
        verbose_name_plural = "วิชา"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

    def user_has_access(self, user) -> bool:
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if self.owner_id == user.pk:
            return True
        return self.shared_with_users.filter(pk=user.pk).exists()


class CourseTag(models.Model):
    """A tag attached to a course for organisation and filtering."""

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="tags",
        db_column="course_id",
        verbose_name="วิชา",
    )
    tag = models.CharField(max_length=100, verbose_name="แท็ก")

    class Meta:
        unique_together = [("course", "tag")]
        ordering = ["tag"]
        verbose_name = "แท็กวิชา"
        verbose_name_plural = "แท็กวิชา"

    def __str__(self) -> str:
        return self.tag
