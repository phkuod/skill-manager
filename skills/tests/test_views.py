import json
import os
import shutil

import pytest
from django.test import Client, TestCase, override_settings

SKILL_REPO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'skill_repo')
)
VERSION_FIXTURE = os.path.join(SKILL_REPO_PATH, 'webapp-testing', '20260331-version-test')


def _create_version_fixture():
    os.makedirs(VERSION_FIXTURE, exist_ok=True)
    with open(os.path.join(VERSION_FIXTURE, 'SKILL.md'), 'w') as f:
        f.write(
            '---\n'
            'name: webapp-testing\n'
            'description: "Versioned webapp testing skill"\n'
            'license: Complete terms in LICENSE.txt\n'
            '---\n\n'
            'Versioned content for webapp-testing.\n'
        )


def _remove_version_fixture():
    if os.path.exists(VERSION_FIXTURE):
        shutil.rmtree(VERSION_FIXTURE, ignore_errors=True)


@pytest.fixture(scope='module', autouse=True)
def version_fixture():
    _remove_version_fixture()
    _create_version_fixture()
    # Re-load skills after creating fixture
    import skills.watcher as watcher
    from skills.parser import parse_all_skills
    watcher._skills = parse_all_skills(SKILL_REPO_PATH)
    yield
    _remove_version_fixture()


@pytest.fixture
def client():
    return Client()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health_status(client, version_fixture):
    res = client.get('/api/health')
    assert res.status_code == 200
    data = res.json()
    assert data['status'] == 'ok'
    assert data['skillCount'] == 17


# ---------------------------------------------------------------------------
# Skill list
# ---------------------------------------------------------------------------

def test_list_all_skills(client, version_fixture):
    res = client.get('/api/skills')
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data['skills'], list)
    assert len(data['skills']) == 17
    assert isinstance(data['categories'], list)
    assert data['categories'][0] == 'All'


def test_list_includes_content_for_search(client, version_fixture):
    # `content` is included in the list response so the home-page search
    # can match against the full SKILL.md body, not just name/description.
    res = client.get('/api/skills')
    for skill in res.json()['skills']:
        assert 'content' in skill


def test_list_required_fields(client, version_fixture):
    res = client.get('/api/skills')
    skill = res.json()['skills'][0]
    for field in ['name', 'description', 'category', 'icon', 'license', 'fileCount', 'lastUpdated', 'currentVersion', 'versions']:
        assert field in skill, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Search filter
# ---------------------------------------------------------------------------

def test_search_by_name(client, version_fixture):
    res = client.get('/api/skills?search=pdf')
    assert res.status_code == 200
    names = [s['name'] for s in res.json()['skills']]
    assert 'pdf' in names


def test_search_by_description(client, version_fixture):
    res = client.get('/api/skills?search=claude')
    assert res.status_code == 200
    assert len(res.json()['skills']) > 0


def test_search_case_insensitive(client, version_fixture):
    lower = client.get('/api/skills?search=pdf').json()['skills']
    upper = client.get('/api/skills?search=PDF').json()['skills']
    assert len(lower) == len(upper)


def test_search_no_matches(client, version_fixture):
    res = client.get('/api/skills?search=xyznonexistent')
    assert res.status_code == 200
    assert res.json()['skills'] == []


def test_search_name_matches_first(client, version_fixture):
    res = client.get('/api/skills?search=api')
    skills = res.json()['skills']
    if len(skills) > 1:
        assert 'api' in skills[0]['name'].lower()


# ---------------------------------------------------------------------------
# Category filter
# ---------------------------------------------------------------------------

def test_category_filter(client, version_fixture):
    res = client.get('/api/skills?category=Tools')
    assert res.status_code == 200
    for s in res.json()['skills']:
        assert s['category'] == 'Tools'


def test_category_all(client, version_fixture):
    res = client.get('/api/skills?category=All')
    assert len(res.json()['skills']) == 17


def test_category_nonexistent(client, version_fixture):
    res = client.get('/api/skills?category=Nonexistent')
    assert res.json()['skills'] == []


def test_search_and_category(client, version_fixture):
    res = client.get('/api/skills?search=pdf&category=Tools')
    assert res.status_code == 200
    skills = res.json()['skills']
    for s in skills:
        assert s['category'] == 'Tools'
    names = [s['name'] for s in skills]
    assert 'pdf' in names


def test_search_matches_content(client, version_fixture):
    # `pypdf` only appears in the body of the pdf SKILL.md, not in name
    # or description. Content search should still surface it.
    res = client.get('/api/skills?search=pypdf')
    assert res.status_code == 200
    names = [s['name'] for s in res.json()['skills']]
    assert 'pdf' in names


def test_search_ranks_name_above_content(client, version_fixture):
    # 'pdf' matches the pdf skill's name and likely appears in other skills'
    # content. The name match must rank first.
    res = client.get('/api/skills?search=pdf')
    skills = res.json()['skills']
    assert len(skills) > 0
    assert skills[0]['name'] == 'pdf'


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def test_pagination_envelope_when_under_limit(client, version_fixture):
    # No params, fewer skills than the default limit: every skill fits on
    # page 1, hasNext is False, no Link header is emitted.
    res = client.get('/api/skills')
    data = res.json()
    for key in ('skills', 'page', 'limit', 'total', 'hasNext'):
        assert key in data, f"Pagination envelope missing key: {key}"
    assert data['page'] == 1
    assert data['limit'] == 50
    assert data['total'] == len(data['skills'])
    assert data['hasNext'] is False
    assert 'Link' not in res


def test_pagination_first_page_with_custom_limit(client, version_fixture):
    res = client.get('/api/skills?limit=5')
    data = res.json()
    assert len(data['skills']) == 5
    assert data['page'] == 1
    assert data['limit'] == 5
    assert data['hasNext'] is True


def test_pagination_second_page(client, version_fixture):
    page1 = client.get('/api/skills?limit=5').json()['skills']
    page2 = client.get('/api/skills?page=2&limit=5').json()['skills']
    assert len(page2) == 5
    page1_names = {s['name'] for s in page1}
    page2_names = {s['name'] for s in page2}
    assert page1_names.isdisjoint(page2_names)


def test_pagination_out_of_range_returns_empty(client, version_fixture):
    res = client.get('/api/skills?page=999&limit=5')
    data = res.json()
    assert data['skills'] == []
    assert data['hasNext'] is False


def test_pagination_limit_clamped_to_max(client, version_fixture):
    res = client.get('/api/skills?limit=99999')
    data = res.json()
    assert data['limit'] == 200


def test_pagination_link_header_present(client, version_fixture):
    res = client.get('/api/skills?limit=5')
    assert 'Link' in res
    assert 'page=2' in res['Link']
    assert 'rel="next"' in res['Link']


# ---------------------------------------------------------------------------
# List projection (no rendered HTML on the wire)
# ---------------------------------------------------------------------------

def test_list_excludes_contentHtml(client, version_fixture):
    # `contentHtml` is the sanitized rendered markdown (~5 KB per skill).
    # The home page never reads it from the list response, so we strip it
    # to keep the inline #skills-data JSON small.
    res = client.get('/api/skills')
    for skill in res.json()['skills']:
        assert 'contentHtml' not in skill, (
            f"List response leaks contentHtml for {skill.get('name')}"
        )


def test_list_keeps_fields_used_by_home_page(client, version_fixture):
    # home.js matchRank reads name/description/content; cards render
    # name/icon/description/fileCount/lastUpdated. All must survive the
    # projection.
    res = client.get('/api/skills')
    for skill in res.json()['skills']:
        for field in ('name', 'icon', 'description', 'fileCount',
                      'lastUpdated', 'content'):
            assert field in skill, (
                f"List projection dropped a field still used by the UI: {field}"
            )


# ---------------------------------------------------------------------------
# Skill detail
# ---------------------------------------------------------------------------

def test_detail_with_content(client, version_fixture):
    res = client.get('/api/skills/pdf')
    assert res.status_code == 200
    data = res.json()
    assert data['name'] == 'pdf'
    assert data['content']
    assert len(data['content']) > 0


def test_detail_install_paths(client, version_fixture):
    res = client.get('/api/skills/pdf')
    paths = res.json()['installPaths']
    assert paths['claudeCode'] == '~/.claude/skills/pdf'
    assert paths['opencode'] == '~/.opencode/skills/pdf'


def test_detail_repo_path(client, version_fixture):
    res = client.get('/api/skills/pdf')
    repo_path = res.json()['repoPath']
    assert 'skill_repo' in repo_path
    assert 'pdf' in repo_path


def test_detail_all_metadata(client, version_fixture):
    res = client.get('/api/skills/frontend-design')
    data = res.json()
    for field in ['name', 'description', 'category', 'icon', 'license', 'fileCount', 'lastUpdated', 'content', 'installPaths', 'repoPath']:
        assert field in data, f"Missing field: {field}"


def test_detail_404(client, version_fixture):
    res = client.get('/api/skills/nonexistent')
    assert res.status_code == 404
    assert 'nonexistent' in res.json()['error']


# ---------------------------------------------------------------------------
# ZIP download
# ---------------------------------------------------------------------------

def test_zip_download(client, version_fixture):
    res = client.get('/api/skills/brand-guidelines/zip')
    assert res.status_code == 200
    assert res['Content-Type'] == 'application/zip'
    assert 'brand-guidelines.zip' in res['Content-Disposition']


def test_zip_nonempty(client, version_fixture):
    res = client.get('/api/skills/brand-guidelines/zip')
    body = b''.join(res.streaming_content)
    assert len(body) > 0


def test_zip_archive_contains_skill_md(client, version_fixture):
    # End-to-end correctness: the streamed bytes must be a valid ZIP that
    # contains the skill's SKILL.md. Catches any regression in the streaming
    # plumbing (truncation, wrong seek position, etc.).
    import io
    import zipfile
    res = client.get('/api/skills/brand-guidelines/zip')
    body = b''.join(res.streaming_content)
    with zipfile.ZipFile(io.BytesIO(body)) as zf:
        names = zf.namelist()
    assert 'SKILL.md' in names


def test_zip_404(client, version_fixture):
    res = client.get('/api/skills/nonexistent/zip')
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------

def test_versions_list(client, version_fixture):
    res = client.get('/api/skills/webapp-testing/versions')
    assert res.status_code == 200
    data = res.json()
    assert data['skill'] == 'webapp-testing'
    assert data['currentVersion'] is not None
    assert isinstance(data['versions'], list)
    assert len(data['versions']) >= 2


def test_versions_unversioned(client, version_fixture):
    res = client.get('/api/skills/pdf/versions')
    assert res.status_code == 200
    data = res.json()
    assert data['currentVersion'] is None
    assert data['versions'] == []


def test_versions_404(client, version_fixture):
    res = client.get('/api/skills/nonexistent/versions')
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Version detail
# ---------------------------------------------------------------------------

def test_version_detail(client, version_fixture):
    res = client.get('/api/skills/webapp-testing/versions/20260331-version-test')
    assert res.status_code == 200
    data = res.json()
    assert data['name'] == 'webapp-testing'
    assert 'Versioned content' in data['content']


def test_version_original(client, version_fixture):
    res = client.get('/api/skills/webapp-testing/versions/original')
    assert res.status_code == 200
    data = res.json()
    assert data['name'] == 'webapp-testing'
    assert data['content']


def test_version_404_bad_version(client, version_fixture):
    res = client.get('/api/skills/webapp-testing/versions/99990101-fake')
    assert res.status_code == 404


def test_version_404_bad_skill(client, version_fixture):
    res = client.get('/api/skills/nonexistent/versions/original')
    assert res.status_code == 404


def test_version_404_original_on_unversioned(client, version_fixture):
    res = client.get('/api/skills/pdf/versions/original')
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Version ZIP
# ---------------------------------------------------------------------------

def test_version_zip(client, version_fixture):
    res = client.get('/api/skills/webapp-testing/versions/20260331-version-test/zip')
    assert res.status_code == 200
    assert res['Content-Type'] == 'application/zip'


def test_version_zip_original(client, version_fixture):
    res = client.get('/api/skills/webapp-testing/versions/original/zip')
    assert res.status_code == 200
    assert res['Content-Type'] == 'application/zip'


def test_version_zip_404(client, version_fixture):
    res = client.get('/api/skills/webapp-testing/versions/99990101-fake/zip')
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Version files
# ---------------------------------------------------------------------------

def test_version_files(client, version_fixture):
    res = client.get('/api/skills/webapp-testing/versions/20260331-version-test/files')
    assert res.status_code == 200
    files = res.json()
    assert isinstance(files, list)
    paths = [f['path'] for f in files]
    assert 'SKILL.md' in paths


def test_version_files_404(client, version_fixture):
    res = client.get('/api/skills/webapp-testing/versions/99990101-fake/files')
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Path-traversal protection on the <version> segment
# ---------------------------------------------------------------------------

def test_version_files_dotdot_rejected(client, version_fixture):
    # `..` as the version segment must not be allowed to walk above the
    # skill directory. A 200 here would leak every skill's files.
    res = client.get('/api/skills/webapp-testing/versions/../files')
    assert res.status_code == 404


def test_version_zip_dotdot_rejected(client, version_fixture):
    res = client.get('/api/skills/webapp-testing/versions/../zip')
    assert res.status_code == 404


def test_version_detail_dotdot_rejected(client, version_fixture):
    res = client.get('/api/skills/webapp-testing/versions/..')
    assert res.status_code == 404


def test_version_files_unknown_version_rejected(client, version_fixture):
    # An unknown version that is not in the catalog must be rejected even
    # if a directory of that name happens to exist on disk.
    res = client.get('/api/skills/webapp-testing/versions/some-fake-version/files')
    assert res.status_code == 404


def test_version_original_files_rejected_for_unversioned(client, version_fixture):
    # 'original' is only valid for skills that have versions. The 'pdf'
    # skill has none, so /versions/original/files must 404.
    res = client.get('/api/skills/pdf/versions/original/files')
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# HTML views (Django templates)
# ---------------------------------------------------------------------------

def test_home_renders_html(client, version_fixture):
    res = client.get('/')
    assert res.status_code == 200
    assert res['Content-Type'].startswith('text/html')


def test_home_contains_skill_name_in_initial_html(client, version_fixture):
    # Server-rendering contract: skill card links must be present in the raw
    # HTML response, not injected by JS after page load.
    res = client.get('/')
    body = res.content.decode('utf-8')
    assert 'href="/skills/pdf/"' in body or 'href="/skills/claude-api/"' in body


def test_skill_detail_renders_html(client, version_fixture):
    res = client.get('/skills/pdf/')
    assert res.status_code == 200
    assert res['Content-Type'].startswith('text/html')


def test_skill_detail_contains_skill_name(client, version_fixture):
    res = client.get('/skills/pdf/')
    body = res.content.decode('utf-8')
    assert 'pdf' in body  # name appears in the rendered HTML


def test_skill_detail_404_for_missing_skill(client, version_fixture):
    res = client.get('/skills/does-not-exist/')
    assert res.status_code == 404


def test_version_detail_renders_html(client, version_fixture):
    res = client.get('/skills/webapp-testing/v/20260331-version-test/')
    assert res.status_code == 200
    body = res.content.decode('utf-8')
    assert 'webapp-testing' in body


def test_version_detail_404_for_missing_version(client, version_fixture):
    res = client.get('/skills/webapp-testing/v/99999999-fake/')
    assert res.status_code == 404
