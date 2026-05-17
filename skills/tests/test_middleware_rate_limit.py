"""H2 — X-Forwarded-For must not bypass the install rate limiter unless
TRUST_PROXY is configured."""
import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from skills.middleware import InstallRateLimitMiddleware


@pytest.fixture(autouse=True)
def _tighten_limits(settings):
    settings.INSTALL_RATE_LIMIT_MAX = 1
    settings.INSTALL_RATE_LIMIT_WINDOW = 60
    yield


@pytest.fixture
def rf():
    return RequestFactory()


def _fresh_middleware():
    """Return a middleware instance with its own empty bucket dict so tests
    don't share state."""
    return InstallRateLimitMiddleware(lambda _req: HttpResponse(status=200))


@pytest.mark.django_db
def test_xff_does_not_split_bucket_without_trust_proxy(settings, rf):
    settings.TRUST_PROXY = False
    mw = _fresh_middleware()
    r1 = rf.post('/api/skills/x/install', REMOTE_ADDR='10.0.0.1',
                 HTTP_X_FORWARDED_FOR='1.1.1.1')
    r2 = rf.post('/api/skills/x/install', REMOTE_ADDR='10.0.0.1',
                 HTTP_X_FORWARDED_FOR='2.2.2.2')
    assert mw(r1).status_code == 200
    # Same REMOTE_ADDR → same bucket → second hits the limit despite XFF spoof.
    assert mw(r2).status_code == 429


@pytest.mark.django_db
def test_xff_splits_bucket_when_trust_proxy_set(settings, rf):
    settings.TRUST_PROXY = True
    mw = _fresh_middleware()
    r1 = rf.post('/api/skills/x/install', REMOTE_ADDR='10.0.0.1',
                 HTTP_X_FORWARDED_FOR='1.1.1.1')
    r2 = rf.post('/api/skills/x/install', REMOTE_ADDR='10.0.0.1',
                 HTTP_X_FORWARDED_FOR='2.2.2.2')
    assert mw(r1).status_code == 200
    assert mw(r2).status_code == 200


@pytest.mark.django_db
def test_xff_rightmost_used_when_trust_proxy_set(settings, rf):
    """The trusted proxy appends to XFF; only the right-most entry is the
    proxy's own assessment of the caller."""
    settings.TRUST_PROXY = True
    mw = _fresh_middleware()
    # Both requests have the SAME right-most XFF entry → same bucket.
    r1 = rf.post('/api/skills/x/install', REMOTE_ADDR='10.0.0.1',
                 HTTP_X_FORWARDED_FOR='evil1, 9.9.9.9')
    r2 = rf.post('/api/skills/x/install', REMOTE_ADDR='10.0.0.1',
                 HTTP_X_FORWARDED_FOR='evil2, 9.9.9.9')
    assert mw(r1).status_code == 200
    assert mw(r2).status_code == 429
