import pytest
from django.test import Client


@pytest.mark.django_db
def test_install_targets_returns_name_and_base_only(settings):
    settings.INSTALL_TARGETS = {
        'F12': {'type': 'local', 'base': '/AAA/{user_name}/skills'},
        'F15': {
            'type': 'ssh',
            'base': '/AAA/{user_name}/skills',
            'host': 'secret.host',
            'user': 'svc',
            'ssh_key': '/etc/ssh/secret',
        },
    }
    resp = Client().get('/api/install/targets')
    assert resp.status_code == 200
    data = resp.json()
    targets = sorted(data['targets'], key=lambda t: t['name'])
    assert targets == [
        {'name': 'F12', 'base': '/AAA/{user_name}/skills'},
        {'name': 'F15', 'base': '/AAA/{user_name}/skills'},
    ]
    body = resp.content.decode('utf-8')
    assert 'secret.host' not in body
    assert 'svc' not in body
    assert 'secret' not in body
