"""C2 defence-in-depth: _install_ssh must shell-quote ssh_key in rsync -e."""
import pytest

from skills import installer


@pytest.fixture
def fake_src(tmp_path):
    src = tmp_path / 'src'
    src.mkdir()
    (src / 'SKILL.md').write_text('---\nname: x\n---\n')
    return str(src)


def test_install_ssh_quotes_ssh_key_in_rsync_e(monkeypatch, fake_src, settings):
    settings.INSTALL_TIMEOUT_SECONDS = 60
    captured = {}

    class _CP:
        returncode = 0
        stderr = b''
        stdout = b''

    def fake_run(cmd, **kwargs):
        captured['cmd'] = cmd
        return _CP()

    monkeypatch.setattr(installer.subprocess, 'run', fake_run)

    cfg = {
        'type': 'ssh',
        'host': 'host.example',
        'user': 'svc',
        'ssh_key': '/tmp/has space.key',
    }
    installer._install_ssh(fake_src, '/srv/user/skills/x', cfg)

    cmd = captured['cmd']
    e_index = cmd.index('-e')
    ssh_arg = cmd[e_index + 1]
    assert '/tmp/has space.key' in ssh_arg
    # shlex.quote uses single quotes on POSIX; on Windows mslex/quote may
    # use double quotes. Accept either, but the bare unquoted form (which
    # rsync's shell would split) must NOT be present.
    bare = 'ssh -i /tmp/has space.key '
    assert bare not in ssh_arg
