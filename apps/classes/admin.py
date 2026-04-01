import datetime

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils import timezone

from apps.faces.models import FaceGroup
from apps.sessions.models import Session

from .forms import AutoCreateSessionsForm, DaySlotFormSet
from .models import Course, CourseTag

User = get_user_model()


class CourseTagInline(admin.TabularInline):
    model = CourseTag
    extra = 1
    fields = ("tag",)
    verbose_name = "แท็ก"
    verbose_name_plural = "แท็ก"


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "shorthand", "owner", "face_group", "tag_list", "created_at")
    list_filter = ("face_group",)
    search_fields = ("name", "description", "tags__tag")
    inlines = [CourseTagInline]
    readonly_fields = ("owner", "created_at", "updated_at")
    filter_horizontal = ("shared_with_users",)
    fieldsets = (
        (None, {
            "fields": ("name", "shorthand", "owner", "shared_with_users", "face_group", "description"),
        }),
        ("เวลาบันทึก", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="แท็ก")
    def tag_list(self, obj):
        return ", ".join(obj.tags.values_list("tag", flat=True))

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.accessible_to(request.user)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "shared_with_users" in form.base_fields:
            qs = User.objects.exclude(pk=request.user.pk).order_by("username")
            if not request.user.is_superuser:
                qs = qs.filter(is_superuser=False)
            form.base_fields["shared_with_users"].queryset = qs
        return form

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "face_group":
            face_groups = FaceGroup.objects.all()
            if not request.user.is_superuser:
                face_groups = FaceGroup.objects.accessible_to(request.user)
            if request.resolver_match and request.resolver_match.kwargs.get("object_id"):
                object_id = request.resolver_match.kwargs["object_id"]
                current_course = Course.objects.filter(pk=object_id).select_related("face_group").first()
                if current_course and current_course.face_group_id:
                    face_groups = (face_groups | FaceGroup.objects.filter(pk=current_course.face_group_id)).distinct()
            kwargs["queryset"] = face_groups
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change and obj.owner_id is None:
            obj.owner = request.user
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:course_id>/auto-create-sessions/",
                self.admin_site.admin_view(self.auto_create_sessions_view),
                name="classes_course_auto_create_sessions",
            ),
        ]
        return custom_urls + urls

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if not request.user.is_superuser and not Course.objects.accessible_to(request.user).filter(pk=object_id).exists():
            raise Http404
        extra_context = extra_context or {}
        extra_context["auto_create_sessions_url"] = reverse(
            "admin:classes_course_auto_create_sessions",
            args=[object_id],
        )
        return super().change_view(request, object_id, form_url, extra_context)

    def auto_create_sessions_view(self, request, course_id):
        course_queryset = Course.objects.all()
        if not request.user.is_superuser:
            course_queryset = Course.objects.accessible_to(request.user)
        course = get_object_or_404(course_queryset, pk=course_id)

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

                            session_name = f"{current.strftime('%Y-%m-%d')} {course.shorthand}"

                            Session.objects.create(
                                course=course,
                                name=session_name,
                                state=Session.State.CLOSED,
                                scheduled_at=aware_start,
                                auto_close_at=aware_end,
                            )
                            created_count += 1
                    current += delta

                self.message_user(
                    request,
                    f"สร้างคาบเรียนสำเร็จ {created_count} คาบ สำหรับวิชา {course.name}",
                    messages.SUCCESS,
                )
                return HttpResponseRedirect(
                    reverse("admin:classes_course_change", args=[course.pk])
                )
        else:
            form = AutoCreateSessionsForm()
            formset = DaySlotFormSet(prefix="slots")

        context = {
            **self.admin_site.each_context(request),
            "title": f"สร้างคาบเรียนอัตโนมัติสำหรับ {course.name}",
            "course": course,
            "form": form,
            "formset": formset,
            "opts": self.model._meta,
        }
        return render(request, "admin/classes/class/auto_create_sessions.html", context)
