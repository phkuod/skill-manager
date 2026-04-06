import os

from django.apps import AppConfig


class SkillsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'skills'

    def ready(self):
        from django.conf import settings
        # Avoid double-init in Django's auto-reloader (runserver spawns two processes)
        if os.environ.get('RUN_MAIN') == 'true' or not settings.DEBUG:
            from . import watcher
            watcher.init_watcher(settings.SKILL_REPO_PATH)
