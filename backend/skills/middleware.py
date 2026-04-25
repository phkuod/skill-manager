import os

from django.http import HttpResponse


class ApiCorsMiddleware:
    """Permissive CORS for /api/* so the frontend can be deployed on a
    different origin (host/port) from the Django backend.

    Origin is controlled by the CORS_ALLOWED_ORIGINS env var.
    - Default '*'  allows any origin (fine for internal tools).
    - For a locked-down deploy, set a single origin like
      'https://skills.example.com'. Browsers do not support a comma-separated
      list here; run a reverse proxy or extend this middleware if you need
      per-request logic.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.allow_origin = os.environ.get('CORS_ALLOWED_ORIGINS', '*')

    def __call__(self, request):
        is_api = request.path.startswith('/api/')

        if is_api and request.method == 'OPTIONS':
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        if is_api:
            response['Access-Control-Allow-Origin'] = self.allow_origin
            response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type'
            response['Vary'] = 'Origin'

        return response
