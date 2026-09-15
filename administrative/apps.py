from django.apps import AppConfig


class AdministrativeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "administrative"

    def ready(self):
        from . import signals
