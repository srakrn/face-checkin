from django.contrib import admin

from .models import Class, ClassTag


class ClassTagInline(admin.TabularInline):
    model = ClassTag
    extra = 1
    fields = ("tag",)
    verbose_name = "แท็ก"
    verbose_name_plural = "แท็ก"


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ("name", "face_group", "tag_list", "created_at")
    list_filter = ("face_group",)
    search_fields = ("name", "description", "tags__tag")
    inlines = [ClassTagInline]
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {
            "fields": ("name", "face_group", "description"),
        }),
        ("เวลาบันทึก", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="แท็ก")
    def tag_list(self, obj):
        return ", ".join(obj.tags.values_list("tag", flat=True))
