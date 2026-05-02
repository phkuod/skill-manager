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

ROOT_URLCONF = 'skill_market.urls'
WSGI_APPLICATION = 'skill_market.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

APPEND_SLASH = False

FRONTEND_DIR = Path(os.environ.get('FRONTEND_DIR', str(BASE_DIR.parent / 'frontend')))

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [FRONTEND_DIR]
WHITENOISE_MANIFEST_STRICT = False

SKILL_REPO_PATH = os.environ.get('SKILL_REPO_PATH', str(BASE_DIR.parent / 'skill_repo'))

INSTALL_TARGETS = {}
_install_target_re = re.compile(r'^INSTALL_TARGET_([A-Z0-9]+)_(.+)$')
for _k, _v in os.environ.items():
    _m = _install_target_re.match(_k)
    if _m:
        _name, _field = _m.group(1), _m.group(2).lower()
        INSTALL_TARGETS.setdefault(_name, {})[_field] = _v

INSTALL_TIMEOUT_SECONDS = int(os.environ.get('INSTALL_TIMEOUT_SECONDS', '60'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
