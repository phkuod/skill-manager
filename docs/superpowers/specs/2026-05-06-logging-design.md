# Logging Design — Skill Market

**Date:** 2026-05-06  
**Status:** Approved

## Goal

Add structured file + console logging so system behaviour can be traced without an external service.

## Configuration (`settings.py`)

Add a `LOGGING` dict using Django's standard logging infrastructure. No new dependencies.

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '{asctime} [{levelname}] {name}: {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.environ.get('LOG_FILE', 'logs/skill-market.log'),
            'maxBytes': int(os.environ.get('LOG_MAX_BYTES', str(10 * 1024 * 1024))),
            'backupCount': int(os.environ.get('LOG_BACKUP_COUNT', '5')),
            'formatter': 'standard',
            'delay': True,
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': os.environ.get('LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'skills': {
            'handlers': ['console', 'file'],
            'level': os.environ.get('LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}
```

`delay=True` prevents crash on startup if `logs/` does not exist and suppresses log file creation during pytest runs.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_FILE` | `logs/skill-market.log` | Log file path |
| `LOG_LEVEL` | `INFO` | Minimum log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_MAX_BYTES` | `10485760` (10 MB) | Max size per log file before rotation |
| `LOG_BACKUP_COUNT` | `5` | Number of rotated files to keep |

## Log Format

```
2026-05-06 14:32:01 [INFO] skills.installer: install success: skill=pdf → /AAA/phkuo/skills/pdf (312ms)
```

`{timestamp} [{level}] {logger_name}: {message}`

## Events to Log Per Module

Each module declares: `logger = logging.getLogger('skills.<module>')`

### `apps.py`
```
INFO   watcher initialized (skill_repo={path}, {n} skills loaded)
```

### `watcher.py`
```
INFO   parse_all_skills started (path={path})
INFO   parse_all_skills completed ({n} skills in {ms}ms)
DEBUG  FS event detected: {event_type} {path} — debounce reset
WARNING  skill parse failed: {skill_name} — {error}
ERROR  watchdog observer failed to start: {error}
```

### `parser.py`
```
WARNING  failed to parse {skill_dir}/SKILL.md: {error}
WARNING  markdown render failed for {skill_name}, falling back to empty string: {error}
```

### `installer.py`
```
INFO   install requested: skill={name} user={user} target={target}
INFO   install success: skill={name} → {path} ({ms}ms)
ERROR  install failed: skill={name} user={user} target={target} — {error}
```

### `views.py`
No logging added — HTTP layer is handled by Django's own request logging.

## File System

- `logs/` added to `.gitignore`
- `logs/.gitkeep` committed to repo so the directory exists on fresh checkout

## Files Changed

| File | Change |
|------|--------|
| `skill_market/settings.py` | Add `LOGGING` dict |
| `skills/apps.py` | Add logger, INFO on init |
| `skills/watcher.py` | Add logger, INFO/DEBUG/WARNING/ERROR events |
| `skills/parser.py` | Add logger, WARNING on parse/render failure + try/except |
| `skills/installer.py` | Add logger, INFO on request/success, ERROR on failure |
| `.gitignore` | Add `logs/` |
| `logs/.gitkeep` | New empty file |
| `.env.example` | Document LOG_FILE, LOG_LEVEL, LOG_MAX_BYTES, LOG_BACKUP_COUNT |
