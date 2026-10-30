from django.apps import AppConfig


class HousingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'housing'

    def ready(self):
        from . import signals  # noqa: F401  (connects the housing demand receivers)
