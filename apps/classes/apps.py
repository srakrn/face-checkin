from django.apps import AppConfig


class ClassesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.classes"
    verbose_name = "วิชา"

    def ready(self):
        from . import signals  # noqa: F401
