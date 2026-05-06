import pytest
from skills.classifier import classify, get_categories


def test_classify_development_skills():
    assert classify('frontend-design') == {'category': 'Development', 'icon': '🎨'}
    assert classify('web-artifacts-builder') == {'category': 'Development', 'icon': '🌐'}
    assert classify('mcp-builder') == {'category': 'Development', 'icon': '🔧'}
    assert classify('skill-creator') == {'category': 'Development', 'icon': '⚡'}


def test_classify_content_skills():
    assert classify('doc-coauthoring') == {'category': 'Content', 'icon': '📝'}
    assert classify('internal-comms') == {'category': 'Content', 'icon': '📢'}
    assert classify('brand-guidelines') == {'category': 'Content', 'icon': '🏷️'}
    assert classify('slack-gif-creator') == {'category': 'Content', 'icon': '🎬'}


def test_classify_tools_skills():
    assert classify('pdf') == {'category': 'Tools', 'icon': '📄'}
    assert classify('docx') == {'category': 'Tools', 'icon': '📃'}
    assert classify('pptx') == {'category': 'Tools', 'icon': '📊'}
    assert classify('xlsx') == {'category': 'Tools', 'icon': '📈'}
    assert classify('canvas-design') == {'category': 'Tools', 'icon': '🖼️'}
    assert classify('theme-factory') == {'category': 'Tools', 'icon': '🎭'}


def test_classify_data_ai_skills():
    assert classify('claude-api') == {'category': 'Data & AI', 'icon': '🤖'}
    assert classify('algorithmic-art') == {'category': 'Data & AI', 'icon': '🎆'}


def test_classify_testing_skills():
    assert classify('webapp-testing') == {'category': 'Testing', 'icon': '🧪'}


def test_classify_unknown_skill():
    assert classify('unknown-skill') == {'category': 'Other', 'icon': '📦'}


def test_classify_empty_string():
    assert classify('') == {'category': 'Other', 'icon': '📦'}


def test_get_categories_all_first():
    categories = get_categories()
    assert categories[0] == 'All'


def test_get_categories_includes_all_defined():
    categories = get_categories()
    assert 'Development' in categories
    assert 'Content' in categories
    assert 'Tools' in categories
    assert 'Data & AI' in categories
    assert 'Testing' in categories


def test_get_categories_no_other():
    categories = get_categories()
    assert 'Other' not in categories


def test_get_categories_sorted_no_duplicates():
    categories = get_categories()
    without_all = categories[1:]
    assert without_all == sorted(without_all)
    assert len(categories) == len(set(categories))


# --- frontmatter overrides ---

def test_classify_frontmatter_overrides_map():
    # Frontmatter should win over CATEGORY_MAP for a known skill name.
    meta = {'category': 'Custom', 'icon': '✨'}
    assert classify('frontend-design', meta) == {'category': 'Custom', 'icon': '✨'}


def test_classify_frontmatter_partial_override():
    # Only `category` provided — icon falls back to CATEGORY_MAP entry.
    meta = {'category': 'Custom'}
    assert classify('frontend-design', meta) == {'category': 'Custom', 'icon': '🎨'}


def test_classify_frontmatter_for_unknown_skill():
    # Unknown skill + frontmatter category: skip the 'Other' default.
    meta = {'category': 'Custom', 'icon': '🎯'}
    assert classify('brand-new-skill', meta) == {'category': 'Custom', 'icon': '🎯'}


def test_classify_empty_meta_uses_fallback():
    assert classify('frontend-design', {}) == {'category': 'Development', 'icon': '🎨'}


def test_get_categories_includes_observed():
    skills = {
        'a': {'category': 'Custom Cat'},
        'b': {'category': 'Development'},  # already in map, no duplicate
    }
    cats = get_categories(skills)
    assert 'Custom Cat' in cats
    # No duplicates
    assert len(cats) == len(set(cats))


def test_get_categories_excludes_other_even_if_observed():
    skills = {'x': {'category': 'Other'}}
    assert 'Other' not in get_categories(skills)
