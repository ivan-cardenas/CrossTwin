from django.apps import AppConfig



class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

class RastersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rasters'

    def ready(self):
        import core.signals  # activates the auto-export