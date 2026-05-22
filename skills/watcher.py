import logging
import threading
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from . import usage
from .parser import parse_all_skills

logger = logging.getLogger('skills.watcher')

_skills = {}
_lock = threading.Lock()
_debounce_timer = None
_skill_repo_path = None
_observer = None


def get_skills():
    return _skills


def _reload():
    global _skills
    if _skill_repo_path is None:
        return
    t0 = time.monotonic()
    try:
        new_skills = parse_all_skills(_skill_repo_path)
    except Exception as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        logger.error('parse_all_skills failed in %dms: %s', elapsed, exc)
        usage.record_event(
            'parse_error',
            latency_ms=elapsed,
            extra={'error': str(exc)[:200]},
        )
        return
    with _lock:
        _skills = new_skills
    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info('parse_all_skills completed (%d skills in %dms)', len(new_skills), elapsed)
    usage.record_event(
        'parse',
        latency_ms=elapsed,
        extra={'skillCount': len(new_skills)},
    )


class _SkillEventHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        global _debounce_timer
        logger.debug('FS event detected: %s %s — debounce reset', event.event_type, event.src_path)
        with _lock:
            if _debounce_timer is not None:
                _debounce_timer.cancel()
            _debounce_timer = threading.Timer(0.3, _reload)
            _debounce_timer.start()


def init_watcher(skill_repo_path):
    global _skill_repo_path, _observer

    _skill_repo_path = skill_repo_path
    logger.info('parse_all_skills started (path=%s)', skill_repo_path)
    _reload()

    handler = _SkillEventHandler()
    _observer = Observer()
    _observer.schedule(handler, skill_repo_path, recursive=True)
    try:
        _observer.start()
    except Exception as exc:
        logger.error('watchdog observer failed to start: %s', exc)
