import os
import re
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env', override=True)

DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1')

SECRET_KEY = os.environ.get('SECRET_KEY') or (
    'dev-insecure-key-change-in-production' if DEBUG else None
)
if not SECRET_KEY:
    raise RuntimeError(
        'SECRET_KEY env var is required when DEBUG=False'
    )

_raw_hosts = os.environ.get('ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(',') if h.strip()]
if not DEBUG and (not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS):
    raise RuntimeError(
        "ALLOWED_HOSTS must be set to explicit hosts (no '*') when DEBUG=False"
    )
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'skills',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'skills.middleware.SecurityHeadersMiddleware',
    'skills.middleware.ApiCorsMiddleware',
    'skills.middleware.InstallRateLimitMiddleware',
    'django.middleware.common.CommonMiddleware',
]

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.request',
        ],
    },
}]

ROOT_URLCONF = 'skill_market.urls'
WSGI_APPLICATION = 'skill_market.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

APPEND_SLASH = False

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
WHITENOISE_MANIFEST_STRICT = False

SKILL_REPO_PATH = os.environ.get('SKILL_REPO_PATH', str(BASE_DIR / 'skill_repo'))

CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', '*')
if not DEBUG and CORS_ALLOWED_ORIGINS.strip() in ('', '*'):
    raise RuntimeError(
        "CORS_ALLOWED_ORIGINS must be set to an explicit origin (not '*') "
        "when DEBUG=False — wildcard + credentials lets any site issue "
        "credentialed cross-origin requests."
    )

INSTALL_TARGETS = {}
_install_target_re = re.compile(r'^INSTALL_TARGET_([A-Z0-9]+)_(.+)$')
for _k, _v in os.environ.items():
    _m = _install_target_re.match(_k)
    if _m:
        _name, _field = _m.group(1), _m.group(2).lower()
        INSTALL_TARGETS.setdefault(_name, {})[_field] = _v

# Reject shell-injectable SSH target config at startup. ssh_key flows through
# rsync's `-e` (shell-expanded); host/user flow through argv but a malformed
# value still produces broken or wrong-host connections.
_ssh_user_re = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_.-]*$')
_ssh_host_re = re.compile(r'^[A-Za-z0-9][A-Za-z0-9.-]*$')
_ssh_key_bad_chars = set('\t\n\r"\'$\\|;&<>()*?{}[] `')
for _tname, _cfg in INSTALL_TARGETS.items():
    if _cfg.get('type') != 'ssh':
        continue
    for _required in ('host', 'user', 'ssh_key'):
        if not _cfg.get(_required):
            raise RuntimeError(
                f"INSTALL_TARGET_{_tname}_{_required.upper()} is required for ssh targets"
            )
    if not _ssh_host_re.match(_cfg['host']):
        raise RuntimeError(
            f"INSTALL_TARGET_{_tname}_HOST has invalid characters: {_cfg['host']!r}"
        )
    if not _ssh_user_re.match(_cfg['user']):
        raise RuntimeError(
            f"INSTALL_TARGET_{_tname}_USER has invalid characters: {_cfg['user']!r}"
        )
    if any(c in _ssh_key_bad_chars for c in _cfg['ssh_key']):
        raise RuntimeError(
            f"INSTALL_TARGET_{_tname}_SSH_KEY contains shell metacharacters; "
            f"path must be free of whitespace and shell special chars"
        )

INSTALL_TIMEOUT_SECONDS = int(os.environ.get('INSTALL_TIMEOUT_SECONDS', '60'))

# Only trust X-Forwarded-For when an upstream reverse proxy is enforcing it.
# When False, the install rate-limiter keys off REMOTE_ADDR so a direct caller
# cannot spoof their bucket via the header.
TRUST_PROXY = os.environ.get('TRUST_PROXY', 'False').lower() in ('true', '1')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

_LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
if _LOG_LEVEL not in {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}:
    import sys
    print(f'[skill-market] WARNING: invalid LOG_LEVEL={_LOG_LEVEL!r}, falling back to INFO', file=sys.stderr)
    _LOG_LEVEL = 'INFO'

try:
    _LOG_MAX_BYTES = int(os.environ.get('LOG_MAX_BYTES', str(10 * 1024 * 1024)))
except ValueError:
    _LOG_MAX_BYTES = 10 * 1024 * 1024

try:
    _LOG_BACKUP_COUNT = int(os.environ.get('LOG_BACKUP_COUNT', '5'))
except ValueError:
    _LOG_BACKUP_COUNT = 5

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
            'maxBytes': _LOG_MAX_BYTES,
            'backupCount': _LOG_BACKUP_COUNT,
            'formatter': 'standard',
            'encoding': 'utf-8',
            'delay': True,
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': _LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'skills': {
            'handlers': ['console', 'file'],
            'level': _LOG_LEVEL,
            'propagate': False,
        },
    },
}
