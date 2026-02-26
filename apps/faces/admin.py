import json

import numpy as np
from django.contrib import admin

from .models import Face, FaceGroup


class FaceInline(admin.TabularInline):
    model = Face
    extra = 0
    fields = ("custom_id", "name", "remarks", "photo")
    readonly_fields = ("created_at", "updated_at")


@admin.register(FaceGroup)
class FaceGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "face_count", "created_at")
    search_fields = ("name",)
    inlines = [FaceInline]

    @admin.display(description="Faces")
    def face_count(self, obj):
        return obj.faces.count()


@admin.register(Face)
class FaceAdmin(admin.ModelAdmin):
    list_display = ("name", "custom_id", "face_group", "has_embedding", "created_at")
    list_filter = ("face_group",)
    search_fields = ("name", "custom_id", "remarks")

    # Exclude the binary embedding field from the admin form — it is managed
    # via the webcam capture widget (stored in the hidden face_embedding_json field).
    exclude = ("embedding",)

    # Show embedding status and timestamps as read-only info in the change form
    readonly_fields = ("has_embedding", "created_at", "updated_at")

    fieldsets = (
        (None, {
            "fields": ("face_group", "custom_id", "name", "remarks", "photo"),
        }),
        ("Enrollment", {
            "fields": ("has_embedding",),
            "description": (
                "Use the 'Capture from webcam' button above the photo field to "
                "capture a photo and extract the face embedding automatically."
            ),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    # Custom change form template that injects the webcam capture widget
    change_form_template = "admin/faces/face/change_form.html"

    @admin.display(boolean=True, description="Has embedding")
    def has_embedding(self, obj):
        return bool(obj.embedding)

    def save_model(self, request, obj, form, change):
        """
        Persist the face embedding submitted via the hidden ``face_embedding_json``
        form field (populated by the webcam capture widget).

        If the webcam widget extracted an embedding it stores it as a JSON array
        in that hidden field.  We read it here and attach it to the object before
        saving, for both new and existing records.

        If no new embedding was submitted for an existing record, we re-fetch the
        current embedding from the DB so it is not silently overwritten with None
        by the admin form (which has no embedding widget).
        """
        embedding_json = request.POST.get("face_embedding_json", "").strip()

        if embedding_json:
            # Webcam widget provided a fresh embedding — use it.
            try:
                embedding_list = json.loads(embedding_json)
                if isinstance(embedding_list, list) and len(embedding_list) == 128:
                    obj.embedding = np.array(
                        embedding_list, dtype=np.float32
                    ).tobytes()
            except (json.JSONDecodeError, ValueError, TypeError):
                pass  # malformed data — fall through to DB-preservation logic below

        if not obj.embedding and change and obj.pk:
            # No new embedding submitted — preserve whatever is already in the DB.
            try:
                current = Face.objects.only("embedding").get(pk=obj.pk)
                obj.embedding = current.embedding
            except Face.DoesNotExist:
                pass

        super().save_model(request, obj, form, change)
