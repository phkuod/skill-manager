import os
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
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'skill_market.urls'
WSGI_APPLICATION = 'skill_market.wsgi.application'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.request',
            'django.template.context_processors.static',
        ],
    },
}]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

APPEND_SLASH = False

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'skills' / 'static']
WHITENOISE_MANIFEST_STRICT = False

SKILL_REPO_PATH = os.environ.get('SKILL_REPO_PATH', str(BASE_DIR.parent / 'skill_repo'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
