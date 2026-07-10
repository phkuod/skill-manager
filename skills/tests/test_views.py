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
    assert isinstance(data['skillCount'], int)
    assert data['skillCount'] >= 1


# ---------------------------------------------------------------------------
# Skill list
# ---------------------------------------------------------------------------

def test_list_all_skills(client, version_fixture):
    res = client.get('/api/skills')
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data['skills'], list)
    assert len(data['skills']) > 0
    # Default limit (50) > test fixture total (~18), so the page contains
    # everything and len(skills) matches `total` from the pagination envelope.
    assert data['total'] == len(data['skills'])


def test_list_includes_content_for_search(client, version_fixture):
    # `content` is included in the list response so the home-page search
    # can match against the full SKILL.md body, not just name/description.
    res = client.get('/api/skills')
    for skill in res.json()['skills']:
        assert 'content' in skill


def test_list_required_fields(client, version_fixture):
    # Mirrors _LIST_FIELDS in views.py — fields the home page actually
    # consumes. `category` was removed when the category system was dropped;
    # `license` was removed by the list-projection slimming.
    res = client.get('/api/skills')
    skill = res.json()['skills'][0]
    for field in ['name', 'description', 'icon', 'fileCount', 'lastUpdated',
                  'currentVersion', 'versions']:
        assert field in skill, f"Missing field: {field}"


_KNOWN_CATEGORIES = {
    'Design', 'Tools', 'Code', 'Content', 'Testing', 'AI/ML',
    'Communication', 'Other',
}


def test_list_includes_category_field(client, version_fixture):
    res = client.get('/api/skills')
    skill = res.json()['skills'][0]
    assert 'category' in skill
    assert skill['category'] in _KNOWN_CATEGORIES


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


def test_detail_does_not_leak_repo_path(client, version_fixture):
    res = client.get('/api/skills/pdf')
    assert 'repoPath' not in res.json()


def test_detail_all_metadata(client, version_fixture):
    res = client.get('/api/skills/frontend-design')
    data = res.json()
    for field in ['name', 'description', 'icon', 'license', 'fileCount',
                  'lastUpdated', 'content', 'installPaths']:
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
    # Regression: 'original' must resolve to the un-versioned top-level
    # SKILL.md. Passing the top-level dir back through parse_skill() (which
    # re-runs version auto-detection) would find the fixture's newer version
    # subdirectory again and wrongly return its content instead.
    assert 'Versioned content' not in data['content']
    assert 'Web Application Testing' in data['content']


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


def test_home_shows_featured_shelf_for_large_catalog(client, version_fixture):
    # Real skill_repo fixture has 17 skills (see test_parse_all_real_repo), well
    # above the 4-skill threshold, so the Featured shelf must render.
    res = client.get('/')
    body = res.content.decode('utf-8')
    assert 'Featured' in body


def test_home_hides_featured_shelf_for_small_catalog(client, monkeypatch):
    import skills.views as views

    def _tiny_skill(name, updated):
        return {
            'name': name, 'icon': '📦', 'category': 'Other', 'description': '',
            'fileCount': 1, 'lastUpdated': updated, 'content': '',
            'currentVersion': None, 'versions': [],
        }

    tiny = {
        'a': _tiny_skill('a', '2026-01-01T00:00:00+00:00'),
        'b': _tiny_skill('b', '2026-01-02T00:00:00+00:00'),
    }
    monkeypatch.setattr(views, 'get_skills', lambda: tiny)
    res = client.get('/')
    body = res.content.decode('utf-8')
    assert 'Featured' not in body


def test_home_category_rail(client, version_fixture):
    res = client.get('/')
    body = res.content.decode('utf-8')
    assert 'class="rail"' in body
    assert 'data-cat=""' in body          # "All" item
    assert 'rail-count' in body           # per-category counts
    assert 'id="category-select"' not in body


def test_home_page_head_replaces_hero(client, version_fixture):
    res = client.get('/')
    body = res.content.decode('utf-8')
    assert 'hero-kicker' not in body
    assert 'Browse skills' in body


def test_home_selects_have_aria_labels(client, version_fixture):
    # Visible "Category:" / "Sort:" labels were replaced by aria-labels in
    # the refined toolbar.
    res = client.get('/')
    body = res.content.decode('utf-8')
    assert 'aria-label="Sort skills"' in body
    assert 'for="category-select"' not in body
    assert 'for="sort-select"' not in body


def test_home_card_shows_category_badge(client, version_fixture):
    res = client.get('/')
    body = res.content.decode('utf-8')
    assert 'category-badge' in body


def test_home_card_category_badge_in_footer(client, version_fixture):
    # Refined card layout: the category badge lives in the footer meta row,
    # which renders *after* the inline-confirm slot in card markup. In the
    # old layout the badge sat in the top row (before the slot).
    res = client.get('/')
    body = res.content.decode('utf-8')
    assert 'data-confirm-slot' in body and 'category-badge' in body
    assert body.index('data-confirm-slot') < body.index('category-badge')


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


def test_version_detail_original_shows_original_content(client, version_fixture):
    # Regression: the HTML route for the synthetic 'original' version must
    # render the top-level SKILL.md's own content, not the newest version
    # subdirectory's content (see test_version_original for the API-level
    # equivalent of this bug).
    res = client.get('/skills/webapp-testing/v/original/')
    assert res.status_code == 200
    body = res.content.decode('utf-8')
    assert 'Web Application Testing' in body
    assert 'Versioned content for webapp-testing' not in body


def test_skill_detail_shows_license_badge(client, version_fixture):
    res = client.get('/skills/pdf/')
    body = res.content.decode('utf-8')
    assert 'license-badge' in body


def test_skill_detail_shows_version_popover(client, version_fixture):
    # Multi-version skills 302-redirect the bare /skills/<name>/ URL to
    # /skills/<name>/v/<currentVersion>/ (see views.skill_detail) — this is
    # pre-existing behavior, unrelated to this task. follow=True so we assert
    # against the final rendered page rather than the redirect response.
    res = client.get('/skills/webapp-testing/', follow=True)
    body = res.content.decode('utf-8')
    assert 'id="version-popover"' in body
    assert 'version-popover-item' in body


def test_skill_detail_quiet_panel_headers(client, version_fixture):
    # Traffic-light window dots were replaced by quiet panel headers.
    res = client.get('/skills/pdf/')
    body = res.content.decode('utf-8')
    assert 'bg-red-500' not in body
    assert 'panel-header' in body


def test_skill_detail_classed_action_buttons(client, version_fixture):
    res = client.get('/skills/pdf/')
    body = res.content.decode('utf-8')
    assert 'btn-accent' in body
    assert 'btn-outline' in body


# ---------------------------------------------------------------------------
# Design tokens & fonts (Task 1: UI foundation)
# ---------------------------------------------------------------------------

def test_base_includes_tokens_css(client):
    html = client.get('/').content.decode()
    assert 'skills/css/tokens.css' in html
    # tokens must load BEFORE app.css so app.css can consume the variables
    assert html.index('skills/css/tokens.css') < html.index('skills/css/app.css')


def test_tokens_css_defines_new_identity():
    from django.contrib.staticfiles import finders
    path = finders.find('skills/css/tokens.css')
    assert path, 'tokens.css not found by staticfiles finders'
    css = open(path, encoding='utf-8').read()
    assert '@font-face' in css
    assert 'InterVariable.woff2' in css
    assert 'JetBrainsMono-Regular.woff2' in css
    assert '--accent: #0284c7' in css
    assert '--bg-primary: #0a0a0c' in css  # dark canvas


def test_vendored_fonts_are_valid_woff2():
    from django.contrib.staticfiles import finders
    for rel in ('skills/vendor/fonts/InterVariable.woff2',
                'skills/vendor/fonts/JetBrainsMono-Regular.woff2',
                'skills/vendor/fonts/JetBrainsMono-Bold.woff2'):
        path = finders.find(rel)
        assert path, rel + ' missing'
        with open(path, 'rb') as f:
            magic = f.read(4)
        assert magic == b'wOF2', rel + ' is not a woff2 file'


def test_app_css_no_longer_defines_tokens():
    from django.contrib.staticfiles import finders
    css = open(finders.find('skills/css/app.css'), encoding='utf-8').read()
    assert '--accent: #4f46e5' not in css      # old light accent gone
    assert '--bg-primary: #0f172a' not in css  # old dark canvas gone


# ---------------------------------------------------------------------------
# Shared shell — single sticky nav in base.html (Task 2: UI redesign)
# ---------------------------------------------------------------------------

def test_site_nav_on_all_pages(client):
    for url in ('/', '/installed/', '/contribute/', '/contributions/'):
        html = client.get(url).content.decode()
        assert 'class="site-nav"' in html, url
        assert 'id="palette-trigger"' in html, url
        assert 'id="theme-toggle"' in html, url


def test_home_old_header_gone(client):
    html = client.get('/').content.decode()
    assert '🛍️' not in html                      # old emoji brand
    assert 'id="search-input"' in html            # search survives, relocated


def test_nav_marks_current_page(client):
    home = client.get('/').content.decode()
    installed = client.get('/installed/').content.decode()
    assert 'href="/" aria-current="page"' in home.replace('\n', ' ')
    assert 'href="/installed/" id="nav-installed" aria-current="page"' in installed.replace('\n', ' ')


# ---------------------------------------------------------------------------
# Command palette (Task 3: Ctrl/Cmd+K global search overlay)
# ---------------------------------------------------------------------------

def test_command_palette_markup_on_every_page(client):
    for url in ('/', '/installed/', '/contribute/'):
        html = client.get(url).content.decode()
        assert 'id="cmd-palette"' in html, url
        assert 'id="cmd-palette-input"' in html, url
        assert 'role="dialog"' in html, url


# ---------------------------------------------------------------------------
# Card redesign + single renderer (Task 4: featured merged into one grid)
# ---------------------------------------------------------------------------

def test_home_cards_merged_single_grid(client):
    import re
    html = client.get('/').content.decode()
    names = re.findall(r'data-name="([^"]+)"', html)
    assert names, 'cards must carry data-name'
    assert len(names) == len(set(names)), 'featured cards must not duplicate grid cards'
    # the standalone Featured shelf is gone; featured skills are tagged in-grid
    assert '<h2 class="shelf-heading">Featured</h2>' not in html
    assert 'card-featured-tag' in html  # real repo has 12+ skills → featured exists


def test_home_js_single_card_renderer():
    from django.contrib.staticfiles import finders
    js = open(finders.find('skills/js/home.js'), encoding='utf-8').read()
    assert 'function cardHtml' not in js, 'dual renderer must be gone'


# ---------------------------------------------------------------------------
# Skill detail redesign (Task 6: breadcrumb, two-column, sticky sidebar)
# ---------------------------------------------------------------------------

def test_skill_detail_sticky_sidebar(client):
    html = client.get('/skills/pdf/').content.decode()
    assert 'class="detail-side"' in html
    assert 'class="side-card"' in html
    assert 'side-meta' in html
    # actions live in the sidebar now
    assert html.index('class="side-card"') < html.index('id="install-button"')


def test_skill_detail_breadcrumb(client):
    html = client.get('/skills/pdf/').content.decode()
    assert 'aria-label="Breadcrumb"' in html
    assert 'class="crumbs' in html


# ---------------------------------------------------------------------------
# Installed page redesign (Task 7: dev-tool row list)
# ---------------------------------------------------------------------------

def test_installed_page_restyled_no_inline_styles(client):
    html = client.get('/installed/').content.decode()
    assert '<style>' not in html, 'inline style block must move to app.css'
    assert 'installed-tabs-container' in html
    assert 'id="bulk-sync-all"' in html
    assert 'id="installed-search"' in html
    from django.contrib.staticfiles import finders
    assert '.page-title' in open(finders.find('skills/css/app.css'), encoding='utf-8').read()


# ---------------------------------------------------------------------------
# Contribute + My contributions redesign (Task 8: dropzone, shared chips/tables)
# ---------------------------------------------------------------------------

def test_contribute_page_restyled(client):
    html = client.get('/contribute/').content.decode()
    assert '<style>' not in html
    assert 'contrib-drop' in html          # dropzone label
    assert 'req-list' in html              # requirements checklist
    from django.contrib.staticfiles import finders
    css = open(finders.find('skills/css/app.css'), encoding='utf-8').read()
    assert '.btn-accent[disabled]' in css


def test_my_contributions_restyled(client):
    html = client.get('/contributions/').content.decode()
    assert '<style>' not in html
    assert ('empty-state' in html) or ('data-table' in html)


# ---------------------------------------------------------------------------
# Review pages redesign (Task 9: admin queue + contribution detail feed)
# ---------------------------------------------------------------------------

def test_review_templates_use_shared_classes():
    from pathlib import Path
    admin_src = Path('skills/templates/skills/admin_contributions.html').read_text(encoding='utf-8')
    detail_src = Path('skills/templates/skills/contribution_detail.html').read_text(encoding='utf-8')
    for src in (admin_src, detail_src):
        assert '<style>' not in src
        assert 'status-chip' in src
    assert 'seg-control' in admin_src
    assert 'feed-entry' in detail_src


def test_app_css_has_review_components():
    from django.contrib.staticfiles import finders
    css = open(finders.find('skills/css/app.css'), encoding='utf-8').read()
    assert '.feed-entry.ai_reviewer' in css
    assert '.ai-verdict.approve' in css
    assert '#admin-actions' in css


def test_usage_template_no_inline_style():
    from pathlib import Path
    src = Path('skills/templates/skills/usage.html').read_text(encoding='utf-8')
    assert '<style>' not in src


def test_404_template_mono_treatment():
    from pathlib import Path
    src = Path('skills/templates/skills/404.html').read_text(encoding='utf-8')
    assert 'notfound-code' in src
