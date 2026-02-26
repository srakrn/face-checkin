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
    # exclusively via the /faces/<pk>/enroll/ endpoint (webcam capture widget).
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
        Preserve the existing embedding when saving via the admin form.

        The embedding is written exclusively by the /faces/<pk>/enroll/
        endpoint.  A normal admin save must never overwrite it with None,
        which would happen if we called obj.save() on a freshly-bound form
        instance that never had the embedding loaded.
        """
        if change and obj.pk:
            # Re-fetch the current embedding from the DB so it is not lost
            # when the admin form (which has no embedding widget) is saved.
            try:
                current = Face.objects.only("embedding").get(pk=obj.pk)
                obj.embedding = current.embedding
            except Face.DoesNotExist:
                pass
        super().save_model(request, obj, form, change)
