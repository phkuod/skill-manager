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
def test_wildcard_with_origin_echoes_origin_and_sets_credentials(settings):
    settings.CORS_ALLOWED_ORIGINS = '*'
    resp = Client().options(
        '/api/skills/x/install',
        HTTP_ORIGIN='http://frontend.intra.example',
    )
    assert resp.status_code == 204
    assert resp.headers['Access-Control-Allow-Origin'] == 'http://frontend.intra.example'
    assert resp.headers['Access-Control-Allow-Credentials'] == 'true'


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
        HTTP_ORIGIN='http://frontend.intra.example',
    )
    assert resp.headers['Access-Control-Allow-Origin'] == 'http://frontend.intra.example'
    assert resp.headers['Access-Control-Allow-Credentials'] == 'true'


@pytest.mark.django_db
def test_no_origin_header_falls_back_to_configured_value(settings):
    """Non-CORS callers (same-origin browser, curl, server-to-server) get the
    raw configured value — typically '*', which is fine because they won't
    enforce CORS anyway."""
    settings.CORS_ALLOWED_ORIGINS = '*'
    resp = Client().options('/api/skills/x/install')  # no Origin header
    assert resp.headers['Access-Control-Allow-Origin'] == '*'
