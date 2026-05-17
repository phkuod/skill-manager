import pytest
from django.test import Client


@pytest.mark.django_db
def test_options_allows_post_method():
    client = Client()
    resp = client.options('/api/skills/anything/install')
    assert resp.status_code == 204
    methods = resp.headers.get('Access-Control-Allow-Methods', '')
    assert 'POST' in methods
    assert 'GET' in methods
    assert 'OPTIONS' in methods


# ---------------------------------------------------------------------------
# Credentialed CORS (cookie-bearing requests across origins)
#
# When fetch() uses credentials:'include' (our install POST does this so the
# CURRENT_USER_NAME cookie travels), browsers reject responses that:
#   - return Access-Control-Allow-Origin: '*'
#   - omit Access-Control-Allow-Credentials: 'true'
# These tests pin down both behaviours.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_wildcard_with_safe_origin_echoes_and_sets_credentials(settings):
    """Same-host dev Origin: echo + credentials so cookie-bearing fetch works."""
    settings.CORS_ALLOWED_ORIGINS = '*'
    resp = Client().options(
        '/api/skills/x/install',
        HTTP_ORIGIN='http://localhost:8888',
    )
    assert resp.status_code == 204
    assert resp.headers['Access-Control-Allow-Origin'] == 'http://localhost:8888'
    assert resp.headers['Access-Control-Allow-Credentials'] == 'true'


@pytest.mark.django_db
def test_wildcard_with_attacker_origin_omits_credentials(settings):
    """H1 — cross-origin Origin under '*' must NOT receive Allow-Credentials."""
    settings.CORS_ALLOWED_ORIGINS = '*'
    resp = Client().options(
        '/api/skills/x/install',
        HTTP_ORIGIN='http://attacker.example',
    )
    assert resp.status_code == 204
    assert resp.headers['Access-Control-Allow-Origin'] == '*'
    assert 'Access-Control-Allow-Credentials' not in resp.headers


@pytest.mark.django_db
def test_specific_origin_used_verbatim_with_credentials(settings):
    settings.CORS_ALLOWED_ORIGINS = 'https://only-this.example'
    resp = Client().options(
        '/api/skills/x/install',
        HTTP_ORIGIN='http://attacker.example',
    )
    assert resp.status_code == 204
    # Server emits its configured allow-origin verbatim — browser will
    # reject if attacker origin doesn't match.
    assert resp.headers['Access-Control-Allow-Origin'] == 'https://only-this.example'
    assert resp.headers['Access-Control-Allow-Credentials'] == 'true'


@pytest.mark.django_db
def test_post_response_includes_credentials_header(settings):
    """The credential headers must travel on the actual response, not just
    the preflight, otherwise the browser drops the response body."""
    settings.CORS_ALLOWED_ORIGINS = '*'
    settings.INSTALL_TARGETS = {}  # endpoint will reject but headers still set
    resp = Client().get(
        '/api/install/targets',
        HTTP_ORIGIN='http://localhost:8888',
    )
    assert resp.headers['Access-Control-Allow-Origin'] == 'http://localhost:8888'
    assert resp.headers['Access-Control-Allow-Credentials'] == 'true'


@pytest.mark.django_db
def test_no_origin_header_falls_back_to_configured_value(settings):
    """Non-CORS callers (same-origin browser, curl, server-to-server) get the
    raw configured value — typically '*', which is fine because they won't
    enforce CORS anyway."""
    settings.CORS_ALLOWED_ORIGINS = '*'
    resp = Client().options('/api/skills/x/install')  # no Origin header
    assert resp.headers['Access-Control-Allow-Origin'] == '*'


# ---------------------------------------------------------------------------
# M1 — Dev CURRENT_USER_NAME cookie must be HttpOnly
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_dev_current_user_cookie_is_httponly(settings):
    settings.DEBUG = True
    client = Client()
    # No cookie set → middleware should issue one on this GET.
    resp = client.get('/api/health')
    cookie = resp.cookies.get('CURRENT_USER_NAME')
    assert cookie is not None
    assert cookie['httponly']
