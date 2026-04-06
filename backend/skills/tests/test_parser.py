import os
import re
import shutil
import tempfile

import pytest

from skills.parser import parse_skill, parse_all_skills, detect_versions

SKILL_REPO_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', 'skill_repo'
)


@pytest.fixture(scope='module')
def fixtures_dir():
    tmp = tempfile.mkdtemp(prefix='skill-fixtures-')

    # valid-skill: full frontmatter + helper.js
    valid = os.path.join(tmp, 'valid-skill')
    os.makedirs(valid)
    with open(os.path.join(valid, 'SKILL.md'), 'w') as f:
        f.write(
            '---\nname: valid-skill\ndescription: "A test skill for validation"\nlicense: MIT\n---\n\n'
            '# Valid Skill\n\nThis is the content of the skill.\n\n## Usage\n\nUse it for testing.\n'
        )
    with open(os.path.join(valid, 'helper.js'), 'w') as f:
        f.write('export default {}')

    # minimal-skill: empty frontmatter
    minimal = os.path.join(tmp, 'minimal-skill')
    os.makedirs(minimal)
    with open(os.path.join(minimal, 'SKILL.md'), 'w') as f:
        f.write('---\n---\n\nJust content, no metadata.\n')

    # no-skill-md: only README.md
    no_skill = os.path.join(tmp, 'no-skill-md')
    os.makedirs(no_skill)
    with open(os.path.join(no_skill, 'README.md'), 'w') as f:
        f.write('# Not a skill')

    # nested-skill: SKILL.md + nested files
    nested = os.path.join(tmp, 'nested-skill')
    os.makedirs(os.path.join(nested, 'sub', 'deep'), exist_ok=True)
    with open(os.path.join(nested, 'SKILL.md'), 'w') as f:
        f.write('---\nname: nested-skill\ndescription: "Skill with nested files"\nlicense: Apache-2.0\n---\n\nNested skill content.\n')
    with open(os.path.join(nested, 'index.js'), 'w') as f:
        f.write('')
    with open(os.path.join(nested, 'sub', 'util.js'), 'w') as f:
        f.write('')
    with open(os.path.join(nested, 'sub', 'deep', 'config.json'), 'w') as f:
        f.write('{}')

    # versioned-skill
    versioned = os.path.join(tmp, 'versioned-skill')
    os.makedirs(versioned)
    with open(os.path.join(versioned, 'SKILL.md'), 'w') as f:
        f.write('---\nname: versioned-skill\ndescription: "Original version"\nlicense: MIT\n---\n\nOriginal content.\n')

    v1 = os.path.join(versioned, '20260401-initial-release')
    os.makedirs(v1)
    with open(os.path.join(v1, 'SKILL.md'), 'w') as f:
        f.write('---\nname: versioned-skill\ndescription: "First versioned release"\nlicense: MIT\n---\n\nVersion 1 content.\n')

    v2 = os.path.join(versioned, '20260415-dark-mode')
    os.makedirs(v2)
    with open(os.path.join(v2, 'SKILL.md'), 'w') as f:
        f.write('---\nname: versioned-skill\ndescription: "Added dark mode support"\nlicense: MIT\n---\n\nVersion 2 content with dark mode.\n')
    with open(os.path.join(v2, 'helper.js'), 'w') as f:
        f.write('export default {}')

    # broken version (no SKILL.md)
    broken = os.path.join(versioned, '20260420-broken')
    os.makedirs(broken)
    with open(os.path.join(broken, 'README.md'), 'w') as f:
        f.write('# No SKILL.md here')

    # bad format (no dash after date)
    bad_fmt = os.path.join(versioned, '20260501')
    os.makedirs(bad_fmt)
    with open(os.path.join(bad_fmt, 'SKILL.md'), 'w') as f:
        f.write('---\nname: bad-format\n---\n')

    yield tmp

    shutil.rmtree(tmp, ignore_errors=True)


# --- parse_skill tests ---

def test_parse_valid_skill(fixtures_dir):
    skill = parse_skill(os.path.join(fixtures_dir, 'valid-skill'), 'valid-skill')
    assert skill is not None
    assert skill['name'] == 'valid-skill'
    assert skill['description'] == 'A test skill for validation'
    assert skill['license'] == 'MIT'
    assert '# Valid Skill' in skill['content']
    assert '## Usage' in skill['content']


def test_parse_category_and_icon(fixtures_dir):
    skill = parse_skill(os.path.join(fixtures_dir, 'valid-skill'), 'valid-skill')
    assert skill['category'] is not None
    assert skill['icon'] is not None


def test_parse_file_count(fixtures_dir):
    skill = parse_skill(os.path.join(fixtures_dir, 'valid-skill'), 'valid-skill')
    assert skill['fileCount'] == 2  # SKILL.md + helper.js


def test_parse_nested_file_count(fixtures_dir):
    skill = parse_skill(os.path.join(fixtures_dir, 'nested-skill'), 'nested-skill')
    assert skill['fileCount'] == 4  # SKILL.md + index.js + sub/util.js + sub/deep/config.json


def test_parse_last_updated_iso(fixtures_dir):
    skill = parse_skill(os.path.join(fixtures_dir, 'valid-skill'), 'valid-skill')
    assert re.match(r'^\d{4}-\d{2}-\d{2}T', skill['lastUpdated'])


def test_parse_no_skill_md_returns_none(fixtures_dir):
    skill = parse_skill(os.path.join(fixtures_dir, 'no-skill-md'), 'no-skill-md')
    assert skill is None


def test_parse_minimal_fallbacks(fixtures_dir):
    skill = parse_skill(os.path.join(fixtures_dir, 'minimal-skill'), 'minimal-skill')
    assert skill is not None
    assert skill['name'] == 'minimal-skill'
    assert skill['description'] == ''
    assert skill['license'] == 'Unknown'


def test_parse_nonexistent_dir_returns_none(fixtures_dir):
    skill = parse_skill(os.path.join(fixtures_dir, 'does-not-exist'), 'does-not-exist')
    assert skill is None


def test_parse_versioned_reads_latest(fixtures_dir):
    skill = parse_skill(os.path.join(fixtures_dir, 'versioned-skill'), 'versioned-skill')
    assert skill is not None
    assert skill['description'] == 'Added dark mode support'
    assert 'dark mode' in skill['content']


def test_parse_versioned_current_version(fixtures_dir):
    skill = parse_skill(os.path.join(fixtures_dir, 'versioned-skill'), 'versioned-skill')
    assert skill['currentVersion'] == '20260415-dark-mode'


def test_parse_versioned_versions_list(fixtures_dir):
    skill = parse_skill(os.path.join(fixtures_dir, 'versioned-skill'), 'versioned-skill')
    assert skill['versions'] == [
        {'version': '20260415-dark-mode', 'date': '20260415'},
        {'version': '20260401-initial-release', 'date': '20260401'},
        {'version': 'original', 'date': None},
    ]


def test_parse_versioned_file_count(fixtures_dir):
    skill = parse_skill(os.path.join(fixtures_dir, 'versioned-skill'), 'versioned-skill')
    # 20260415-dark-mode has SKILL.md + helper.js = 2
    assert skill['fileCount'] == 2


def test_parse_unversioned_null_version(fixtures_dir):
    skill = parse_skill(os.path.join(fixtures_dir, 'valid-skill'), 'valid-skill')
    assert skill['currentVersion'] is None
    assert skill['versions'] == []


# --- parse_all_skills tests ---

def test_parse_all_returns_dict(fixtures_dir):
    skills = parse_all_skills(fixtures_dir)
    assert isinstance(skills, dict)
    assert len(skills) == 4  # valid, minimal, nested, versioned (no-skill-md skipped)


def test_parse_all_keys(fixtures_dir):
    skills = parse_all_skills(fixtures_dir)
    assert 'valid-skill' in skills
    assert 'minimal-skill' in skills
    assert 'nested-skill' in skills
    assert 'versioned-skill' in skills


def test_parse_all_skips_no_skill_md(fixtures_dir):
    skills = parse_all_skills(fixtures_dir)
    assert 'no-skill-md' not in skills


def test_parse_all_nonexistent_path():
    skills = parse_all_skills('/nonexistent/path/xyz')
    assert isinstance(skills, dict)
    assert len(skills) == 0


def test_parse_all_real_repo():
    repo = os.path.abspath(SKILL_REPO_PATH)
    if not os.path.isdir(repo):
        pytest.skip('skill_repo not found')
    skills = parse_all_skills(repo)
    assert len(skills) == 17
    assert 'pdf' in skills
    assert 'claude-api' in skills
    assert 'frontend-design' in skills


# --- detect_versions tests ---

def test_detect_versions_sorted(fixtures_dir):
    versions = detect_versions(os.path.join(fixtures_dir, 'versioned-skill'))
    assert len(versions) == 2
    assert versions[0]['version'] == '20260415-dark-mode'
    assert versions[1]['version'] == '20260401-initial-release'


def test_detect_versions_has_dates(fixtures_dir):
    versions = detect_versions(os.path.join(fixtures_dir, 'versioned-skill'))
    assert versions[0]['date'] == '20260415'
    assert versions[1]['date'] == '20260401'


def test_detect_versions_ignores_broken(fixtures_dir):
    versions = detect_versions(os.path.join(fixtures_dir, 'versioned-skill'))
    names = [v['version'] for v in versions]
    assert '20260420-broken' not in names


def test_detect_versions_ignores_bad_format(fixtures_dir):
    versions = detect_versions(os.path.join(fixtures_dir, 'versioned-skill'))
    names = [v['version'] for v in versions]
    assert '20260501' not in names


def test_detect_versions_unversioned(fixtures_dir):
    versions = detect_versions(os.path.join(fixtures_dir, 'valid-skill'))
    assert versions == []


def test_detect_versions_nonexistent(fixtures_dir):
    versions = detect_versions(os.path.join(fixtures_dir, 'does-not-exist'))
    assert versions == []
