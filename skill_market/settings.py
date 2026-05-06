import os
import re
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-insecure-key-change-in-production')
DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1')
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'skills',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'skills.middleware.ApiCorsMiddleware',
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

INSTALL_TARGETS = {}
_install_target_re = re.compile(r'^INSTALL_TARGET_([A-Z0-9]+)_(.+)$')
for _k, _v in os.environ.items():
    _m = _install_target_re.match(_k)
    if _m:
        _name, _field = _m.group(1), _m.group(2).lower()
        INSTALL_TARGETS.setdefault(_name, {})[_field] = _v

INSTALL_TIMEOUT_SECONDS = int(os.environ.get('INSTALL_TIMEOUT_SECONDS', '60'))

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
