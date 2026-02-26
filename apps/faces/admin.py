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
    readonly_fields = ("created_at", "updated_at")

    @admin.display(boolean=True, description="Embedding")
    def has_embedding(self, obj):
        return bool(obj.embedding)
