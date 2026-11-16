from django.apps import AppConfig


class UrbanheatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'urban_heat'

    def ready(self):
        import urban_heat.signals  # noqa: F401  (connects the receivers)
        return super().ready()
