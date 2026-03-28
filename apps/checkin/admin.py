from django.contrib import admin

from .models import CheckIn


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ("pk", "session", "face", "matched", "checked_in_at", "ip_address")
    list_filter = ("matched", "session__state", "session__klass__face_group")
    search_fields = ("face__name", "face__custom_id", "session__name", "ip_address")
    readonly_fields = ("checked_in_at", "raw_face_image", "ip_address", "user_agent")
    date_hierarchy = "checked_in_at"

    def get_model_perms(self, request):
        """Hide this model from the admin index / sidebar."""
        return {}
