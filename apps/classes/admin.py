import datetime

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils import timezone

from apps.sessions.models import Session

from .forms import AutoCreateSessionsForm, DaySlotFormSet
from .models import Class, ClassTag


class ClassTagInline(admin.TabularInline):
    model = ClassTag
    extra = 1
    fields = ("tag",)
    verbose_name = "แท็ก"
    verbose_name_plural = "แท็ก"


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ("name", "shorthand", "face_group", "tag_list", "created_at")
    list_filter = ("face_group",)
    search_fields = ("name", "description", "tags__tag")
    inlines = [ClassTagInline]
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {
            "fields": ("name", "shorthand", "face_group", "description"),
        }),
        ("เวลาบันทึก", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="แท็ก")
    def tag_list(self, obj):
        return ", ".join(obj.tags.values_list("tag", flat=True))

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:class_id>/auto-create-sessions/",
                self.admin_site.admin_view(self.auto_create_sessions_view),
                name="classes_class_auto_create_sessions",
            ),
        ]
        return custom_urls + urls

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["auto_create_sessions_url"] = reverse(
            "admin:classes_class_auto_create_sessions",
            args=[object_id],
        )
        return super().change_view(request, object_id, form_url, extra_context)

    def auto_create_sessions_view(self, request, class_id):
        klass = get_object_or_404(Class, pk=class_id)

        if request.method == "POST":
            form = AutoCreateSessionsForm(request.POST)
            formset = DaySlotFormSet(request.POST, prefix="slots")

            if form.is_valid() and formset.is_valid():
                start_date = form.cleaned_data["start_date"]
                end_date = form.cleaned_data["end_date"]

                slots = [
                    f.cleaned_data
                    for f in formset
                    if f.cleaned_data and not f.cleaned_data.get("DELETE", False)
                ]

                created_count = 0
                current = start_date
                delta = datetime.timedelta(days=1)

                while current <= end_date:
                    for slot in slots:
                        dow = int(slot["day_of_week"])
                        if current.weekday() == dow:
                            start_time = slot["start_time"]
                            end_time = slot["end_time"]

                            # Build timezone-aware datetimes
                            naive_start = datetime.datetime.combine(current, start_time)
                            naive_end = datetime.datetime.combine(current, end_time)
                            aware_start = timezone.make_aware(naive_start)
                            aware_end = timezone.make_aware(naive_end)

                            session_name = f"{current.strftime('%Y-%m-%d')} {klass.shorthand}"

                            Session.objects.create(
                                klass=klass,
                                name=session_name,
                                state=Session.State.CLOSED,
                                scheduled_at=aware_start,
                                auto_close_at=aware_end,
                            )
                            created_count += 1
                    current += delta

                self.message_user(
                    request,
                    f"สร้างคาบเรียนสำเร็จ {created_count} คาบ สำหรับวิชา {klass.name}",
                    messages.SUCCESS,
                )
                return HttpResponseRedirect(
                    reverse("admin:classes_class_change", args=[klass.pk])
                )
        else:
            form = AutoCreateSessionsForm()
            formset = DaySlotFormSet(prefix="slots")

        context = {
            **self.admin_site.each_context(request),
            "title": f"สร้างคาบเรียนอัตโนมัติสำหรับ {klass.name}",
            "klass": klass,
            "form": form,
            "formset": formset,
            "opts": self.model._meta,
        }
        return render(request, "admin/classes/class/auto_create_sessions.html", context)
