from django.apps import AppConfig



class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import core.signals  # activates the auto-export

        # The footer's version label runs `git` three times (~0.25 s on
        # Windows). Fetch it in the background when a server starts, so the
        # first page doesn't wait for it. Not for tests or other commands.
        import os
        import sys
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") == "true":
            import threading
            from core.version import _get_git_info
            threading.Thread(target=_get_git_info, name="git-version-prefetch", daemon=True).start()