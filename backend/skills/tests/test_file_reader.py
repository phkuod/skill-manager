import os
import shutil
import tempfile

import pytest

from skills.file_reader import infer_language, read_skill_files

SKILL_REPO_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'skill_repo'
)


# --- infer_language tests ---

def test_infer_markdown():
    assert infer_language('SKILL.md') == 'markdown'
    assert infer_language('shared/models.md') == 'markdown'


def test_infer_python():
    assert infer_language('example.py') == 'python'


def test_infer_typescript():
    assert infer_language('app.ts') == 'typescript'
    assert infer_language('App.tsx') == 'typescript'


def test_infer_javascript():
    assert infer_language('index.js') == 'javascript'
    assert infer_language('App.jsx') == 'javascript'


def test_infer_unknown():
    assert infer_language('LICENSE.txt') == 'text'
    assert infer_language('README') == 'text'


def test_infer_json():
    assert infer_language('config.json') == 'json'


def test_infer_yaml():
    assert infer_language('config.yaml') == 'yaml'
    assert infer_language('config.yml') == 'yaml'


def test_infer_go():
    assert infer_language('main.go') == 'go'


def test_infer_ruby():
    assert infer_language('app.rb') == 'ruby'


def test_infer_java():
    assert infer_language('App.java') == 'java'


def test_infer_csharp():
    assert infer_language('App.cs') == 'csharp'


def test_infer_php():
    assert infer_language('index.php') == 'php'


def test_infer_bash():
    assert infer_language('run.sh') == 'bash'


# --- read_skill_files tests (real repo) ---

def test_read_returns_list():
    path = os.path.join(SKILL_REPO_PATH, 'brand-guidelines')
    if not os.path.isdir(path):
        pytest.skip('skill_repo not found')
    files = read_skill_files(path)
    assert isinstance(files, list)
    assert len(files) > 0


def test_read_skill_md_first():
    path = os.path.join(SKILL_REPO_PATH, 'brand-guidelines')
    if not os.path.isdir(path):
        pytest.skip('skill_repo not found')
    files = read_skill_files(path)
    assert files[0]['path'] == 'SKILL.md'


def test_read_file_fields():
    path = os.path.join(SKILL_REPO_PATH, 'brand-guidelines')
    if not os.path.isdir(path):
        pytest.skip('skill_repo not found')
    files = read_skill_files(path)
    for f in files:
        assert 'path' in f
        assert 'content' in f
        assert 'language' in f


def test_read_unknown_skill():
    path = os.path.join(SKILL_REPO_PATH, 'nonexistent-skill-xyz')
    files = read_skill_files(path)
    assert files == []


def test_read_subdirectories():
    path = os.path.join(SKILL_REPO_PATH, 'claude-api')
    if not os.path.isdir(path):
        pytest.skip('skill_repo not found')
    files = read_skill_files(path)
    paths = [f['path'] for f in files]
    assert 'SKILL.md' in paths
    assert any('/' in p for p in paths)


# --- truncation / binary tests (temp fixtures) ---

@pytest.fixture
def tmp_skill_dir():
    tmp = tempfile.mkdtemp(prefix='skill-file-test-')
    skill_dir = os.path.join(tmp, 'test-skill')
    os.makedirs(skill_dir)
    with open(os.path.join(skill_dir, 'SKILL.md'), 'w') as f:
        f.write('# Test Skill\n')
    yield skill_dir
    shutil.rmtree(tmp, ignore_errors=True)


def test_truncation_over_500kb(tmp_skill_dir):
    big_content = b'x' * (501 * 1024)
    with open(os.path.join(tmp_skill_dir, 'bigfile.txt'), 'wb') as f:
        f.write(big_content)
    files = read_skill_files(tmp_skill_dir)
    big_file = next((f for f in files if f['path'] == 'bigfile.txt'), None)
    assert big_file is not None
    assert big_file.get('truncated') is True
    assert big_file['content'] is None


def test_skip_binary_files(tmp_skill_dir):
    binary_data = bytes([0] * 100)
    with open(os.path.join(tmp_skill_dir, 'image.bin'), 'wb') as f:
        f.write(binary_data)
    files = read_skill_files(tmp_skill_dir)
    assert not any(f['path'] == 'image.bin' for f in files)


def test_include_small_text_files(tmp_skill_dir):
    content = 'This is a small text file\n' * 100
    with open(os.path.join(tmp_skill_dir, 'smallfile.txt'), 'w') as f:
        f.write(content)
    files = read_skill_files(tmp_skill_dir)
    small = next((f for f in files if f['path'] == 'smallfile.txt'), None)
    assert small is not None
    assert small['content'] is not None
    assert 'truncated' not in small
