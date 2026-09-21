from django.apps import AppConfig


class WatersupplyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "watersupply"

    def ready(self):
        from . import signals  # noqa: F401  (connects the receivers)
