import uuid

from django.db import models


class FaceGroup(models.Model):
    """A named collection of enrolled faces (participants)."""

    name = models.CharField(max_length=255, verbose_name="ชื่อกลุ่ม")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="สร้างเมื่อ")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "กลุ่มใบหน้า"
        verbose_name_plural = "กลุ่มใบหน้า"

    def __str__(self) -> str:
        return self.name


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
        default=uuid.uuid4,
        verbose_name="รหัสประจำตัว",
        help_text="รหัสเฉพาะภายในกลุ่มใบหน้า ค่าเริ่มต้นเป็น UUID",
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
