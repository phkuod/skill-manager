import logging

from django.apps import AppConfig
from django.core.signals import request_started

logger = logging.getLogger('skills.apps')


class SkillsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'skills'

    def ready(self):
        # Lazy-init on first HTTP request. This guarantees exactly one init
        # regardless of launcher (runserver autoreload parent vs. child,
        # --noreload, gunicorn) and skips management commands like
        # collectstatic/migrate/pytest that never serve requests.
        request_started.connect(_init_once, dispatch_uid='skills.init_once')


_initialized = False


def _init_once(**_):
    global _initialized
    if _initialized:
        return
    _initialized = True
    from django.conf import settings
    from . import watcher, usage
    logger.info('initializing skill watcher (skill_repo=%s)', settings.SKILL_REPO_PATH)
    watcher.init_watcher(settings.SKILL_REPO_PATH)
    usage.init_usage(settings.USAGE_DB_PATH, settings.USAGE_RETENTION_DAYS)
