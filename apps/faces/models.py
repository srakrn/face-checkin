from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.image_utils import downscale_image_for_storage, jpeg_upload_name


class FaceGroupQuerySet(models.QuerySet):
    def accessible_to(self, user):
        if user.is_superuser:
            return self
        if not user.is_authenticated:
            return self.none()
        return self.filter(Q(owner=user) | Q(shared_with_users=user)).distinct()


class FaceGroup(models.Model):
    """A named collection of enrolled faces (participants)."""

    name = models.CharField(max_length=255, verbose_name="ชื่อกลุ่ม")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_face_groups",
        verbose_name="เจ้าของ",
    )
    shared_with_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="shared_face_groups",
        verbose_name="แชร์กับผู้ใช้",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="สร้างเมื่อ")

    objects = FaceGroupQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "กลุ่มใบหน้า"
        verbose_name_plural = "กลุ่มใบหน้า"

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


class Face(models.Model):
    """An enrolled participant face within a FaceGroup."""

    face_group = models.ForeignKey(
        FaceGroup,
        on_delete=models.CASCADE,
        related_name="faces",
        verbose_name="กลุ่มใบหน้า",
    )
    # custom_id is unique within a face group (not globally)
    custom_id = models.CharField(
        max_length=255,
        verbose_name="รหัสประจำตัว",
        help_text="รหัสเฉพาะภายในกลุ่มใบหน้า",
    )
    name = models.CharField(max_length=255, verbose_name="ชื่อ")
    remarks = models.TextField(blank=True, verbose_name="หมายเหตุ")
    # Embedding stored as raw bytes (numpy array serialised via numpy.tobytes / frombuffer)
    embedding = models.BinaryField(
        blank=True,
        null=True,
        verbose_name="ข้อมูลใบหน้า",
        help_text="เวกเตอร์ข้อมูลใบหน้า 128 มิติ เก็บเป็น float32 bytes",
    )
    photo = models.ImageField(
        upload_to="faces/photos/",
        blank=True,
        null=True,
        verbose_name="รูปภาพ",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="สร้างเมื่อ")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="แก้ไขล่าสุด")

    class Meta:
        # custom_id must be unique within a face group
        unique_together = [("face_group", "custom_id")]
        ordering = ["name"]
        verbose_name = "ใบหน้า"
        verbose_name_plural = "ใบหน้า"

    def __str__(self) -> str:
        return f"{self.name} ({self.custom_id})"

    def save(self, *args, **kwargs):
        photo_field = self.photo
        needs_processing = bool(photo_field) and not getattr(photo_field, "_committed", False)

        if needs_processing:
            photo_file = getattr(photo_field, "file", photo_field)
            photo_name = getattr(photo_field, "name", getattr(photo_file, "name", "image"))
            optimized_photo = downscale_image_for_storage(photo_file)
            self.photo.save(
                jpeg_upload_name(photo_name),
                optimized_photo,
                save=False,
            )
        super().save(*args, **kwargs)
