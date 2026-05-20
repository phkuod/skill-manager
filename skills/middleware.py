import logging
import re
import time
import threading
from collections import defaultdict

from django.conf import settings
from django.http import HttpResponse, JsonResponse

from . import usage

_usage_logger = logging.getLogger('skills.usage')


# Same-host dev origins safe to echo with credentials. Any other Origin gets
# a non-credentialed `*` response, which browsers reject for credentialed
# requests — neutralizing CSRF on /install from arbitrary visited sites.
_DEV_SAFE_ORIGIN_RE = re.compile(r'^https?://(localhost|127\.0\.0\.1)(:\d+)?$')


def get_client_ip(request) -> str:
    """Return the best-guess client IP for the request.

    Honors settings.TRUST_PROXY: when True, takes the right-most entry of
    X-Forwarded-For (the value the trusted upstream proxy itself appended),
    otherwise falls back to REMOTE_ADDR. XFF is attacker-controlled when
    no trusted proxy is in front, so we ignore it by default.
    """
    if getattr(settings, 'TRUST_PROXY', False):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR', '') or ''


class ApiCorsMiddleware:
    """CORS for /api/*.

    Configured via CORS_ALLOWED_ORIGINS (read from settings each request).

    Two modes:
    - Explicit origin (prod): CORS_ALLOWED_ORIGINS='https://skills.example.com'.
      That literal is returned and Allow-Credentials is set unconditionally.
      Browsers do not support comma-separated lists here.
    - Wildcard (dev only): CORS_ALLOWED_ORIGINS='*'. The request Origin is
      echoed with Allow-Credentials ONLY when it matches the safe same-host
      pattern (localhost/127.0.0.1 — see _DEV_SAFE_ORIGIN_RE). Any other
      Origin gets Allow-Origin: '*' with NO Allow-Credentials header, which
      browsers reject for credentialed requests — blocking CSRF on /install
      from arbitrary visited sites in dev.

    Settings.py refuses to boot when DEBUG=False and CORS_ALLOWED_ORIGINS is
    '*' (or empty), so the wildcard branch only runs in dev.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_api = request.path.startswith('/api/')

        if is_api and request.method == 'OPTIONS':
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        if is_api:
            configured = getattr(settings, 'CORS_ALLOWED_ORIGINS', '*')
            request_origin = request.META.get('HTTP_ORIGIN', '')

            credentialed = True
            if configured == '*':
                if request_origin and _DEV_SAFE_ORIGIN_RE.match(request_origin):
                    response['Access-Control-Allow-Origin'] = request_origin
                else:
                    response['Access-Control-Allow-Origin'] = '*'
                    credentialed = False
            else:
                response['Access-Control-Allow-Origin'] = configured

            if credentialed:
                response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type'
            response['Vary'] = 'Origin'

        return response


class SecurityHeadersMiddleware:
    """Add security headers to every response.

    - X-Content-Type-Options: nosniff — prevents MIME type sniffing
    - X-Frame-Options: DENY — prevents clickjacking via iframes
    - Referrer-Policy: strict-origin-when-cross-origin — limits referer leakage
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_cookie = False
        if settings.DEBUG and request.method == 'GET' and not request.COOKIES.get('CURRENT_USER_NAME'):
            import os
            dev_user = os.environ.get('DEV_USER_NAME', 'dev')
            request.COOKIES['CURRENT_USER_NAME'] = dev_user
            set_cookie = True

        response = self.get_response(request)

        if set_cookie:
            import os
            dev_user = os.environ.get('DEV_USER_NAME', 'dev')
            response.set_cookie('CURRENT_USER_NAME', dev_user, path='/', samesite='Lax', httponly=True)

        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response


class InstallRateLimitMiddleware:
    """Simple in-process rate limiter for POST /api/*/install endpoints.

    Uses a per-IP sliding window (default: 10 requests per 60 seconds).
    Returns 429 if the limit is exceeded.

    Env vars:
      INSTALL_RATE_LIMIT_MAX   — max requests per window (default: 10)
      INSTALL_RATE_LIMIT_WINDOW — window in seconds (default: 60)
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._lock = threading.Lock()
        # {ip: [timestamp, ...]}
        self._requests = defaultdict(list)
        self._max = int(getattr(settings, 'INSTALL_RATE_LIMIT_MAX', 10))
        self._window = int(getattr(settings, 'INSTALL_RATE_LIMIT_WINDOW', 60))

    def __call__(self, request):
        if request.method != 'POST' or '/install' not in request.path:
            return self.get_response(request)

        ip = self._get_client_ip(request)
        now = time.monotonic()

        with self._lock:
            # Prune old timestamps
            timestamps = self._requests[ip]
            cutoff = now - self._window
            self._requests[ip] = [t for t in timestamps if t > cutoff]

            if len(self._requests[ip]) >= self._max:
                return JsonResponse(
                    {'error': 'Rate limit exceeded. Try again later.'},
                    status=429,
                )
            self._requests[ip].append(now)

        return self.get_response(request)

    @staticmethod
    def _get_client_ip(request):
        # XFF is attacker-controlled unless a trusted reverse proxy is in
        # front. Only consult it when TRUST_PROXY is set, and take the
        # right-most entry (the value the trusted proxy itself appended).
        if getattr(settings, 'TRUST_PROXY', False):
            forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
            if forwarded:
                return forwarded.split(',')[-1].strip()
        return request.META.get('REMOTE_ADDR', '')


# Path prefixes the usage middleware skips entirely (no point storing them).
_USAGE_SKIP_PREFIXES = ('/static/', '/favicon')

# Detail routes whose URL kwargs include the skill name — used to pull the
# skill out of the resolved match without re-parsing the path.
_USAGE_DETAIL_VIEWS = {
    'skill_detail', 'skill_detail_version',
    'api_skill_detail', 'api_skill_zip', 'api_skill_files',
    'api_skill_install', 'api_versions', 'api_version_detail',
    'api_version_install', 'api_version_zip', 'api_version_files',
    'api_v1_skill_detail', 'api_v1_skill_zip', 'api_v1_skill_files',
    'api_v1_skill_install', 'api_v1_versions', 'api_v1_version_detail',
    'api_v1_version_install', 'api_v1_version_zip', 'api_v1_version_files',
}


class UsageRecordingMiddleware:
    """Capture pageview + api events for the usage dashboard.

    Must NOT raise: usage tracking is a side-channel and must never affect
    the response a user sees. All work is wrapped in try/except with a
    WARNING log on failure.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip noisy static asset traffic before timing anything.
        path = request.path or ''
        if path.startswith(_USAGE_SKIP_PREFIXES):
            return self.get_response(request)

        t0 = time.monotonic()
        response = self.get_response(request)
        latency_ms = int((time.monotonic() - t0) * 1000)

        try:
            self._record(request, response, latency_ms)
        except Exception as exc:
            _usage_logger.warning('usage middleware record failed: %s', exc)

        return response

    @staticmethod
    def _record(request, response, latency_ms):
        path = request.path or ''
        is_api = path.startswith('/api/')
        match = getattr(request, 'resolver_match', None)

        # Unmatched non-API paths produce no useful signal.
        if match is None and not is_api:
            return

        event_type = 'api' if is_api else 'pageview'
        skill = None
        version = None
        if match is not None:
            kwargs = match.kwargs or {}
            if match.url_name in _USAGE_DETAIL_VIEWS:
                skill = kwargs.get('name')
                version = kwargs.get('version')
            else:
                skill = kwargs.get('name')

        user = (request.COOKIES.get('CURRENT_USER_NAME') or '').strip() or None
        ip = get_client_ip(request) or None

        usage.record_event(
            event_type,
            skill=skill,
            version=version,
            user=user,
            status=response.status_code,
            latency_ms=latency_ms,
            extra={'path': path[:200], 'method': request.method},
            ip=ip,
        )
