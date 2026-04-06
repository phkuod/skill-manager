import threading

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .parser import parse_all_skills

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
    new_skills = parse_all_skills(_skill_repo_path)
    with _lock:
        _skills = new_skills


class _SkillEventHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        global _debounce_timer
        with _lock:
            if _debounce_timer is not None:
                _debounce_timer.cancel()
            _debounce_timer = threading.Timer(0.3, _reload)
            _debounce_timer.start()


def init_watcher(skill_repo_path):
    global _skill_repo_path, _observer

    _skill_repo_path = skill_repo_path

    # Initial load
    _reload()

    # Start file watcher
    handler = _SkillEventHandler()
    _observer = Observer()
    _observer.schedule(handler, skill_repo_path, recursive=True)
    _observer.start()
