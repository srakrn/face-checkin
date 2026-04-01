import json

import numpy as np
from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.http import Http404

from .models import Face, FaceGroup

User = get_user_model()


class FaceInlineForm(forms.ModelForm):
    """
    Inline form for Face that includes a hidden ``face_embedding_json`` field.

    The bulk webcam capture widget populates this field with a JSON array of
    128 floats.  ``save()`` reads it and attaches the embedding to the instance
    before persisting — exactly the same pattern used by the single-Face admin.
    """

    face_embedding_json = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Face
        fields = "__all__"
        widgets = {
            "custom_id": forms.TextInput(attrs={"style": "width: 8em;"}),
            "remarks": forms.Textarea(attrs={"rows": 2, "cols": 20, "style": "width: 12em; height: 4em;"}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)

        embedding_json = self.cleaned_data.get("face_embedding_json", "").strip()
        photo_cleared = not self.cleaned_data.get("photo")

        if embedding_json:
            try:
                embedding_list = json.loads(embedding_json)
                if isinstance(embedding_list, list) and len(embedding_list) == 128:
                    instance.embedding = np.array(
                        embedding_list, dtype=np.float32
                    ).tobytes()
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        elif photo_cleared:
            # Photo was removed — clear the embedding too.
            instance.embedding = None
        elif not instance.embedding and instance.pk:
            # No new embedding and photo not cleared — preserve existing embedding.
            try:
                current = Face.objects.only("embedding").get(pk=instance.pk)
                instance.embedding = current.embedding
            except Face.DoesNotExist:
                pass

        if commit:
            instance.save()
            self.save_m2m()
        return instance


class FaceInline(admin.TabularInline):
    model = Face
    form = FaceInlineForm
    extra = 1
    fields = ("custom_id", "name", "photo", "remarks", "has_embedding", "face_embedding_json")
    readonly_fields = ("created_at", "updated_at", "has_embedding")
    verbose_name = "ใบหน้า"
    verbose_name_plural = "ใบหน้า"

    @admin.display(boolean=True, description="มีข้อมูลใบหน้า")
    def has_embedding(self, obj):
        return bool(obj.embedding)


@admin.register(FaceGroup)
class FaceGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "face_count", "created_at")
    search_fields = ("name",)
    inlines = [FaceInline]
    readonly_fields = ("owner", "created_at")
    filter_horizontal = ("shared_with_users",)
    fieldsets = (
        (None, {
            "fields": ("name", "owner", "shared_with_users", "created_at"),
        }),
    )

    # Custom change form template that injects the bulk webcam capture widget
    change_form_template = "admin/faces/facegroup/change_form.html"

    @admin.display(description="จำนวนใบหน้า")
    def face_count(self, obj):
        return obj.faces.count()

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

    def save_model(self, request, obj, form, change):
        if not change and obj.owner_id is None:
            obj.owner = request.user
        super().save_model(request, obj, form, change)


@admin.register(Face)
class FaceAdmin(admin.ModelAdmin):
    list_display = ("name", "custom_id", "face_group", "has_embedding", "created_at")
    list_filter = ("face_group",)
    search_fields = ("name", "custom_id", "remarks")

    def get_model_perms(self, request):
        """Hide this model from the admin index / sidebar."""
        return {}

    # Exclude the binary embedding field from the admin form — it is managed
    # via the webcam capture widget (stored in the hidden face_embedding_json field).
    exclude = ("embedding",)

    # Show embedding status and timestamps as read-only info in the change form
    readonly_fields = ("has_embedding", "created_at", "updated_at")

    fieldsets = (
        (None, {
            "fields": ("face_group", "custom_id", "name", "remarks", "photo"),
        }),
        ("การลงทะเบียนใบหน้า", {
            "fields": ("has_embedding",),
            "description": (
                "ใช้ปุ่ม 'ถ่ายภาพจากกล้อง' เหนือช่องรูปภาพ "
                "เพื่อถ่ายภาพและดึงข้อมูลใบหน้าโดยอัตโนมัติ"
            ),
        }),
        ("เวลาบันทึก", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    # Custom change form template that injects the webcam capture widget
    change_form_template = "admin/faces/face/change_form.html"

    @admin.display(boolean=True, description="มีข้อมูลใบหน้า")
    def has_embedding(self, obj):
        return bool(obj.embedding)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(face_group__in=FaceGroup.objects.accessible_to(request.user)).distinct()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "face_group" and not request.user.is_superuser:
            kwargs["queryset"] = FaceGroup.objects.accessible_to(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_object(self, request, object_id, from_field=None):
        obj = super().get_object(request, object_id, from_field=from_field)
        if obj is None or request.user.is_superuser or obj.face_group.user_has_access(request.user):
            return obj
        raise Http404

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

        If the photo is cleared, the embedding is also cleared.
        """
        embedding_json = request.POST.get("face_embedding_json", "").strip()
        photo_cleared = not form.cleaned_data.get("photo")

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
        elif photo_cleared:
            # Photo was removed — clear the embedding too.
            obj.embedding = None
        elif not obj.embedding and change and obj.pk:
            # No new embedding and photo not cleared — preserve whatever is already in the DB.
            try:
                current = Face.objects.only("embedding").get(pk=obj.pk)
                obj.embedding = current.embedding
            except Face.DoesNotExist:
                pass

        super().save_model(request, obj, form, change)
