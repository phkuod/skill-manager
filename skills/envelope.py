"""Response envelope helpers for /api/v1/*.

The v1 surface uses a unified shape:
- Success: {"data": <payload>, "meta"?: {...}}
- Error:   {"error": {"code": "<CODE>", "message": "<human msg>", "details"?: {...}}}

The legacy /api/* paths keep their pre-existing shapes for backward
compatibility. New clients should use /api/v1/* and key off the error
code string, not the HTTP status, when retrying or branching.
"""
from django.http import JsonResponse


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

SKILL_NOT_FOUND = 'SKILL_NOT_FOUND'
VERSION_NOT_FOUND = 'VERSION_NOT_FOUND'

INVALID_BODY = 'INVALID_BODY'
INSTALL_USERNAME_INVALID = 'INSTALL_USERNAME_INVALID'
INSTALL_TARGET_INVALID = 'INSTALL_TARGET_INVALID'
INSTALL_SOURCE_NOT_FOUND = 'INSTALL_SOURCE_NOT_FOUND'
INSTALL_CONFIG_ERROR = 'INSTALL_CONFIG_ERROR'
INSTALL_FAILED = 'INSTALL_FAILED'
RSYNC_FAILED = 'RSYNC_FAILED'
RSYNC_TIMEOUT = 'RSYNC_TIMEOUT'

RATE_LIMITED = 'RATE_LIMITED'
FILE_TOO_LARGE = 'FILE_TOO_LARGE'


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def ok(data, meta=None, status=200):
    """Wrap successful payload in the v1 envelope."""
    body = {'data': data}
    if meta is not None:
        body['meta'] = meta
    return JsonResponse(body, status=status, safe=False)


def err(code, message, status=400, details=None):
    """Return a structured error response."""
    body = {'error': {'code': code, 'message': message}}
    if details is not None:
        body['error']['details'] = details
    return JsonResponse(body, status=status)
