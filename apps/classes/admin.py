from django.contrib import admin

from .models import Class, ClassTag


class ClassTagInline(admin.TabularInline):
    model = ClassTag
    extra = 1
    fields = ("tag",)


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ("name", "face_group", "tag_list", "created_at")
    list_filter = ("face_group",)
    search_fields = ("name", "description", "tags__tag")
    inlines = [ClassTagInline]
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Tags")
    def tag_list(self, obj):
        return ", ".join(obj.tags.values_list("tag", flat=True))
