from django.contrib import admin

from .models import Session


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("name", "klass", "state", "scheduled_at", "auto_close_at", "created_at")
    list_filter = ("state", "klass__face_group")
    search_fields = ("name", "klass__name")
    readonly_fields = ("created_at", "updated_at")
    actions = ["activate_sessions", "close_sessions"]

    @admin.action(description="Activate selected sessions (Draft → Active)")
    def activate_sessions(self, request, queryset):
        count = 0
        for session in queryset.filter(state=Session.State.DRAFT):
            try:
                session.activate()
                count += 1
            except ValueError:
                pass
        self.message_user(request, f"{count} session(s) activated.")

    @admin.action(description="Close selected sessions (Active → Closed)")
    def close_sessions(self, request, queryset):
        count = 0
        for session in queryset.filter(state=Session.State.ACTIVE):
            try:
                session.close()
                count += 1
            except ValueError:
                pass
        self.message_user(request, f"{count} session(s) closed.")
