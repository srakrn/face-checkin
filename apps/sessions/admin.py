from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Session


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("name", "klass", "state", "scheduled_at", "auto_close_at", "report_link", "kiosk_link", "qr_code_button")
    list_filter = ("state", "klass__face_group")
    search_fields = ("name", "klass__name")
    readonly_fields = ("created_at", "updated_at", "report_link")
    actions = ["activate_sessions", "close_sessions"]
    fieldsets = (
        (None, {
            "fields": ("klass", "name", "state"),
        }),
        ("กำหนดเวลา", {
            "fields": ("scheduled_at", "auto_close_at"),
        }),
        ("ลิงก์", {
            "fields": ("report_link",),
        }),
        ("เวลาบันทึก", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    class Media:
        js = ("admin/js/session_qr.js",)

    @admin.display(description="รายงาน")
    def report_link(self, obj):
        if obj.pk is None:
            return "—"
        url = reverse("sessions:report_page", args=[obj.pk])
        return format_html('<a href="{}" target="_blank">ดูรายงาน →</a>', url)

    @admin.display(description="คีออสก์")
    def kiosk_link(self, obj):
        url = reverse("kiosk:kiosk", args=[obj.pk])
        return format_html('<a href="{}" target="_blank">เปิดคีออสก์ →</a>', url)

    @admin.display(description="QR Code")
    def qr_code_button(self, obj):
        url = reverse("kiosk:kiosk", args=[obj.pk])
        return format_html(
            '<button type="button" class="button"'
            ' data-kiosk-url="{}" data-session-name="{}"'
            ' onclick="showKioskQR(this.dataset.kioskUrl, this.dataset.sessionName)">'
            "แสดง QR"
            "</button>",
            url,
            obj.name,
        )

    @admin.action(description="เปิดใช้งานคาบเรียนที่เลือก (ร่าง → เปิดใช้งาน)")
    def activate_sessions(self, request, queryset):
        count = 0
        for session in queryset.filter(state=Session.State.DRAFT):
            try:
                session.activate()
                count += 1
            except ValueError:
                pass
        self.message_user(request, f"เปิดใช้งาน {count} คาบเรียน")

    @admin.action(description="ปิดคาบเรียนที่เลือก (เปิดใช้งาน → ปิด)")
    def close_sessions(self, request, queryset):
        count = 0
        for session in queryset.filter(state=Session.State.ACTIVE):
            try:
                session.close()
                count += 1
            except ValueError:
                pass
        self.message_user(request, f"ปิด {count} คาบเรียน")
