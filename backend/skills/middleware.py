from django.conf import settings
from django.http import HttpResponse


class ApiCorsMiddleware:
    """Permissive CORS for /api/* so the frontend can be deployed on a
    different origin (host/port) from the Django backend.

    Origin is controlled by the CORS_ALLOWED_ORIGINS env var (read from
    settings.CORS_ALLOWED_ORIGINS each request, so tests can override it).

    - Default '*' allows any origin (fine for an unauthenticated internal
      tool).
    - For a locked-down deploy, set a single origin like
      'https://skills.example.com'. Browsers do not support a comma-separated
      list here; run a reverse proxy or extend this middleware if you need
      per-request logic.

    Credentialed requests: the install POST sends the CURRENT_USER_NAME
    cookie via fetch(..., {credentials:'include'}). Browsers reject
    credentialed responses that return Access-Control-Allow-Origin: '*' or
    omit Access-Control-Allow-Credentials. So when CORS_ALLOWED_ORIGINS='*'
    and the request carries an Origin header, we echo that exact origin back
    instead of '*' and always set Allow-Credentials. The trade-off: any site
    can issue credentialed cross-origin calls, including CSRF-style triggers
    of /install (which only writes to the cookie owner's user dir, but still
    something to be aware of). Lock down by setting CORS_ALLOWED_ORIGINS to
    your actual frontend origin in deployment.
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

            if configured == '*' and request_origin:
                response['Access-Control-Allow-Origin'] = request_origin
            else:
                response['Access-Control-Allow-Origin'] = configured

            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type'
            response['Vary'] = 'Origin'

        return response
