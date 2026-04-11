from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db.models.signals import post_save
from django.dispatch import receiver

PROJECT_PERMISSION_APP_LABELS = ("faces", "classes", "checkin", "checkin_sessions")

User = get_user_model()


@receiver(post_save, sender=User, dispatch_uid="bootstrap_project_user_access")
def bootstrap_project_user_access(sender, instance, created, raw, **kwargs):
    if raw or not created:
        return

    if instance.is_superuser:
        if not instance.is_staff:
            sender.objects.filter(pk=instance.pk).update(is_staff=True)
        return

    if not instance.is_staff:
        sender.objects.filter(pk=instance.pk).update(is_staff=True)
        instance.is_staff = True

    permission_ids = list(
        Permission.objects.filter(
            content_type__app_label__in=PROJECT_PERMISSION_APP_LABELS
        ).values_list("id", flat=True)
    )
    if permission_ids:
        instance.user_permissions.add(*permission_ids)
