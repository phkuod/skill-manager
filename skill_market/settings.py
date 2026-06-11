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
    'skills.middleware.UsageRecordingMiddleware',
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

# Usage dashboard. `USAGE_ADMIN_USERS` gates /usage and /api/usage/* against
# the CURRENT_USER_NAME cookie. Empty set ⇒ dashboard forbidden for everyone
# (fail closed). Events are written to a file-backed SQLite DB separate from
# Django's :memory: default.
USAGE_ADMIN_USERS = {
    u.strip() for u in os.environ.get('USAGE_ADMIN_USERS', '').split(',') if u.strip()
}
USAGE_DB_PATH = os.environ.get('USAGE_DB_PATH', str(BASE_DIR / 'data' / 'usage.sqlite3'))
try:
    USAGE_RETENTION_DAYS = int(os.environ.get('USAGE_RETENTION_DAYS', '90'))
except ValueError:
    USAGE_RETENTION_DAYS = 90

# Only trust X-Forwarded-For when an upstream reverse proxy is enforcing it.
# When False, the install rate-limiter keys off REMOTE_ADDR so a direct caller
# cannot spoof their bucket via the header.
TRUST_PROXY = os.environ.get('TRUST_PROXY', 'False').lower() in ('true', '1')

# Skill contributions. Users submit skill ZIPs that admins review, comment on,
# approve, and then publish. Phase 1: human review/approve, then a separate
# Publish step (admin-clicked). Phase 2 will layer AI review and let the
# submitter click Publish once their submission is approved.
SUBMISSIONS_DB_PATH = os.environ.get(
    'SUBMISSIONS_DB_PATH', str(BASE_DIR / 'data' / 'submissions.sqlite3')
)
SUBMISSIONS_BLOB_DIR = os.environ.get(
    'SUBMISSIONS_BLOB_DIR', str(BASE_DIR / 'data' / 'submissions')
)
try:
    SUBMISSIONS_MAX_ZIP_BYTES = int(
        os.environ.get('SUBMISSIONS_MAX_ZIP_BYTES', str(5 * 1024 * 1024))
    )
except ValueError:
    SUBMISSIONS_MAX_ZIP_BYTES = 5 * 1024 * 1024

# Admins for the contribution queue. Falls back to USAGE_ADMIN_USERS so the
# same operator-level cookie names that view /usage also moderate /contribute
# by default. Empty set ⇒ admin endpoints forbidden for everyone (fail closed).
_skill_review_raw = os.environ.get('SKILL_REVIEW_ADMINS', '').strip()
if _skill_review_raw:
    SKILL_REVIEW_ADMINS = {
        u.strip() for u in _skill_review_raw.split(',') if u.strip()
    }
else:
    SKILL_REVIEW_ADMINS = set(USAGE_ADMIN_USERS)

# AI reviewer (phase 2). Dark by default — ops flips AI_REVIEW_ENABLED=true
# once an API key is in env. One settings block covers OpenRouter today and
# any OpenAI-compatible internal endpoint later (just swap LLM_BASE_URL +
# LLM_API_KEY + AI_REVIEW_MODELS).
AI_REVIEW_ENABLED = os.environ.get('AI_REVIEW_ENABLED', 'False').lower() in ('true', '1')
LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://openrouter.ai/api/v1')
LLM_API_KEY = os.environ.get('LLM_API_KEY', '') or os.environ.get('OPENROUTER_API_KEY', '')
LLM_EXTRA_HEADERS = os.environ.get(
    'LLM_EXTRA_HEADERS',
    'HTTP-Referer=https://skills.local,X-Title=Skill Market AI reviewer',
)
AI_REVIEW_MODELS = [
    m.strip() for m in os.environ.get(
        'AI_REVIEW_MODELS',
        # Strongest free-tier models that support response_format=json_object
        # (checked against /api/v1/models, 2026-06: models without it 4xx on
        # every call and burn the rate budget). openrouter/free is a
        # meta-router that always resolves to a live free model — keeps the
        # chain working when individual free models get delisted.
        'nvidia/nemotron-3-super-120b-a12b:free,'
        'qwen/qwen3-next-80b-a3b-instruct:free,'
        'openrouter/free',
    ).split(',') if m.strip()
]
try:
    AI_REVIEW_MAX_INPUT_TOKENS = int(os.environ.get('AI_REVIEW_MAX_INPUT_TOKENS', '12000'))
except ValueError:
    AI_REVIEW_MAX_INPUT_TOKENS = 12000
try:
    AI_REVIEW_TIMEOUT_S = int(os.environ.get('AI_REVIEW_TIMEOUT_S', '120'))
except ValueError:
    AI_REVIEW_TIMEOUT_S = 120
try:
    AI_REVIEW_RATE_BUDGET_PER_MIN = int(
        os.environ.get('AI_REVIEW_RATE_BUDGET_PER_MIN', '15')
    )
except ValueError:
    AI_REVIEW_RATE_BUDGET_PER_MIN = 15
try:
    AI_REVIEW_CONCURRENT_WORKERS = int(
        os.environ.get('AI_REVIEW_CONCURRENT_WORKERS', '1')
    )
except ValueError:
    AI_REVIEW_CONCURRENT_WORKERS = 1
AI_REVIEW_AUTO_NUDGE = os.environ.get('AI_REVIEW_AUTO_NUDGE', 'always')
try:
    AI_REVIEW_CONFIDENCE_CAP = float(
        os.environ.get('AI_REVIEW_CONFIDENCE_CAP', '0.8')
    )
except ValueError:
    AI_REVIEW_CONFIDENCE_CAP = 0.8
AI_REVIEW_DROP_HALLUCINATED_EVIDENCE = os.environ.get(
    'AI_REVIEW_DROP_HALLUCINATED_EVIDENCE', 'True'
).lower() in ('true', '1')
AI_REVIEW_PRIVACY_NOTICE = os.environ.get(
    'AI_REVIEW_PRIVACY_NOTICE',
    'Reviewed by an external LLM; bundle content may be retained '
    "per the provider's policy.",
)
try:
    AI_REVIEW_RERUN_DAILY_CAP_PER_SUBMISSION = int(
        os.environ.get('AI_REVIEW_RERUN_DAILY_CAP_PER_SUBMISSION', '3')
    )
except ValueError:
    AI_REVIEW_RERUN_DAILY_CAP_PER_SUBMISSION = 3
AI_REVIEW_CATALOG_DETAIL = os.environ.get('AI_REVIEW_CATALOG_DETAIL', 'hashes')

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
