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
