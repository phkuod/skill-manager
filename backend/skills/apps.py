import os

from django.apps import AppConfig


class SkillsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'skills'

    def ready(self):
        from django.conf import settings
        # RUN_MAIN is set to 'true' only in the child process of Django's autoreloader.
        # When --noreload is used or running via gunicorn/WSGI, RUN_MAIN is absent.
        # We init in both the child process and in non-autoreloader contexts,
        # but skip the parent monitor process (where RUN_MAIN == unset AND autoreloader runs).
        run_main = os.environ.get('RUN_MAIN')
        if run_main == 'true' or run_main is None:
            from . import watcher
            watcher.init_watcher(settings.SKILL_REPO_PATH)
