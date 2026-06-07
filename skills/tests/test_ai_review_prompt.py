"""M2 — bundle context + catalog index + prompt composition.

Covers categories D (prompt composition) and the catalog-index slice of
category E from the test plan. These tests never start the worker
thread — they exercise the pure helpers ``_gather_bundle_context``,
``_catalog_index``, and ``_compose_prompt`` directly. The LLM is never
invoked; ``_call_llm`` is not monkey-patched.

Each test sets up a minimal contributions tmp DB so ``create_submission``
works, builds a tailored in-memory ZIP, then inspects either the bundle
dict or the composed prompt string.
"""
from __future__ import annotations

import io
import os
import zipfile

import pytest

from skills import ai_review, contributions


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_zip(files: dict) -> bytes:
    """Build a ZIP from a {path: bytes-or-str} mapping."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            if isinstance(content, str):
                content = content.encode('utf-8')
            zf.writestr(path, content)
    return buf.getvalue()


def _minimal_skill_md(name='m2-test', desc='M2 prompt test skill.') -> str:
    return f'---\nname: {name}\ndescription: {desc}\nlicense: MIT\n---\n\n# {name}\n'


@pytest.fixture
def contrib_ready(tmp_path, settings):
    """contributions initialised, ai_review.config configured (but no worker)."""
    contributions._reset_for_tests()
    ai_review._reset_for_tests()
    contributions.init_submissions(
        str(tmp_path / 'subs.sqlite3'), str(tmp_path / 'blobs'),
    )

    # The prompt helpers read ai_review._config for catalog_detail and
    # max_input_tokens. Drive a minimal valid config without starting
    # the worker thread.
    settings.AI_REVIEW_ENABLED = True
    settings.LLM_BASE_URL = 'http://stub'
    settings.LLM_API_KEY = 'k'
    settings.AI_REVIEW_MODELS = ['stub-model']
    settings.AI_REVIEW_PRIVACY_NOTICE = ''
    settings.AI_REVIEW_CATALOG_DETAIL = 'hashes'
    ai_review._config = ai_review._build_config()

    yield tmp_path

    ai_review._reset_for_tests()
    contributions._reset_for_tests()


# ── _gather_bundle_context ──────────────────────────────────────────────────


def test_gather_returns_skill_md_first_8kb(contrib_ready):
    big_skill_md = _minimal_skill_md() + ('extra line\n' * 2000)
    assert len(big_skill_md) > ai_review._MAX_SKILL_MD_BYTES
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip({'SKILL.md': big_skill_md}),
        original_filename='big.zip',
    )
    bundle = ai_review._gather_bundle_context(sub['id'])
    assert bundle['skill_md']
    assert len(bundle['skill_md']) <= ai_review._MAX_SKILL_MD_BYTES
    # Should start with the frontmatter — we read from byte 0.
    assert bundle['skill_md'].startswith('---\nname: m2-test')


def test_gather_includes_file_tree_capped_at_64_entries(contrib_ready):
    files = {'SKILL.md': _minimal_skill_md()}
    for i in range(80):
        files[f'src/file_{i:02d}.txt'] = f'content {i}\n'
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(files), original_filename='many.zip',
    )
    bundle = ai_review._gather_bundle_context(sub['id'])
    # Cap PLUS the truncation-marker entry → at most 64+1.
    assert len(bundle['file_tree']) <= ai_review._MAX_FILE_TREE_ENTRIES + 1
    # Last entry should be the "(N more files truncated)" marker.
    assert 'truncated' in bundle['file_tree'][-1]['relPath']


def test_gather_prioritises_py_in_code_excerpts(contrib_ready):
    # Three text files: a small .py + a large .txt + a small .md.
    # We expect .py to appear in excerpts even though the .txt is bigger.
    files = {
        'SKILL.md': _minimal_skill_md(),
        'handlers/main.py': 'def hello():\n    return 42\n',
        'docs/notes.txt': 'x' * 12000,   # big but lower priority
        'README.md': '# note\n',          # text but non-code
    }
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(files), original_filename='code.zip',
    )
    bundle = ai_review._gather_bundle_context(sub['id'])
    excerpt_paths = [e['relPath'] for e in bundle['code_excerpts']]
    py_path = next(p for p in excerpt_paths if p.endswith('main.py'))
    py_index = excerpt_paths.index(py_path)
    # The .py file should appear before the .txt one.
    txt_index = next(
        (i for i, p in enumerate(excerpt_paths) if p.endswith('notes.txt')),
        None,
    )
    if txt_index is not None:
        assert py_index < txt_index


def test_gather_truncates_code_excerpts_at_total_16kb(contrib_ready):
    # A single 20 KB code file. Per-file cap is 8 KB, so we should get a
    # truncated excerpt of exactly the per-file limit.
    files = {
        'SKILL.md': _minimal_skill_md(),
        'src/big.py': 'x' * 20000,
    }
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(files), original_filename='big.zip',
    )
    bundle = ai_review._gather_bundle_context(sub['id'])
    total = sum(len(e['content']) for e in bundle['code_excerpts'])
    assert total <= ai_review._MAX_CODE_EXCERPT_TOTAL_BYTES
    py = next(e for e in bundle['code_excerpts'] if e['relPath'].endswith('big.py'))
    assert py['truncated'] is True


def test_gather_marks_truncated_files_with_explicit_flag(contrib_ready):
    files = {
        'SKILL.md': _minimal_skill_md(),
        'main.py': 'x' * (ai_review._MAX_PER_FILE_BYTES + 100),
    }
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(files), original_filename='m.zip',
    )
    bundle = ai_review._gather_bundle_context(sub['id'])
    excerpt = next(e for e in bundle['code_excerpts'] if e['relPath'].endswith('main.py'))
    assert excerpt['truncated'] is True


def test_gather_omits_binary_extensions(contrib_ready):
    files = {
        'SKILL.md': _minimal_skill_md(),
        'assets/logo.png': b'\x89PNG\r\n\x1a\n' + b'\x00' * 200,
        'data/db.sqlite3': b'SQLite format 3\x00binary',
        'src/main.py': 'x = 1\n',
    }
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(files), original_filename='mixed.zip',
    )
    bundle = ai_review._gather_bundle_context(sub['id'])
    excerpt_paths = [e['relPath'] for e in bundle['code_excerpts']]
    assert any(p.endswith('main.py') for p in excerpt_paths)
    assert not any(p.endswith('.png') for p in excerpt_paths)
    assert not any(p.endswith('.sqlite3') for p in excerpt_paths)


def test_gather_omits_binary_without_extension_via_null_byte_probe(contrib_ready):
    files = {
        'SKILL.md': _minimal_skill_md(),
        'opaque_blob': b'header\x00\x01\x02\x03binary',
    }
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(files), original_filename='b.zip',
    )
    bundle = ai_review._gather_bundle_context(sub['id'])
    paths = [e['relPath'] for e in bundle['code_excerpts']]
    assert 'opaque_blob' not in paths


def test_gather_handles_missing_extracted_dir(contrib_ready):
    """If the extracted dir was lost on disk, gather returns empties."""
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip({'SKILL.md': _minimal_skill_md()}),
        original_filename='ok.zip',
    )
    # Wipe the extracted dir manually to simulate corruption.
    import shutil
    blob_root = os.path.join(contributions._blob_dir, str(sub['id']))
    shutil.rmtree(os.path.join(blob_root, 'extracted'), ignore_errors=True)

    bundle = ai_review._gather_bundle_context(sub['id'])
    assert bundle['skill_md'] == ''
    assert bundle['file_tree'] == []
    assert bundle['code_excerpts'] == []


# ── _catalog_index ──────────────────────────────────────────────────────────


def _stub_catalog(monkeypatch, entries):
    """Replace watcher.get_skills() with a controlled fixture."""
    from skills import watcher
    monkeypatch.setattr(watcher, 'get_skills', lambda: entries)


def test_catalog_index_hashes_mode_sends_first_80_chars(contrib_ready, monkeypatch):
    long_desc = 'A' * 500
    _stub_catalog(monkeypatch, {
        'one': {'name': 'One', 'description': long_desc, 'lastUpdated': 100},
    })
    ai_review._config = ai_review._build_config()
    # default detail is hashes
    out = ai_review._catalog_index()
    assert len(out) == 1
    assert out[0]['slug'] == 'one'
    assert out[0]['name'] == 'One'
    # 80-char prefix plus an ellipsis marker (truncation indicator)
    assert out[0]['desc'].startswith('A' * 80)
    assert out[0]['desc'].endswith('…')


def test_catalog_index_full_mode_sends_full_descriptions(contrib_ready, monkeypatch, settings):
    long_desc = 'B' * 300
    _stub_catalog(monkeypatch, {
        'two': {'name': 'Two', 'description': long_desc, 'lastUpdated': 200},
    })
    settings.AI_REVIEW_CATALOG_DETAIL = 'full'
    ai_review._config = ai_review._build_config()
    out = ai_review._catalog_index()
    assert out[0]['desc'] == long_desc


def test_catalog_index_capped_at_60_with_truncation_marker(contrib_ready, monkeypatch):
    entries = {
        f'slug-{i:03d}': {
            'name': f'Skill {i}',
            'description': f'desc {i}',
            'lastUpdated': i,
        }
        for i in range(80)
    }
    _stub_catalog(monkeypatch, entries)
    out = ai_review._catalog_index()
    assert len(out) == ai_review._MAX_CATALOG_INDEX_ENTRIES + 1
    assert out[-1]['slug'] == '__truncated__'
    assert '20' in out[-1]['name']   # 80 - 60 = 20 truncated


def test_catalog_index_orders_by_last_updated_desc(contrib_ready, monkeypatch):
    _stub_catalog(monkeypatch, {
        'old':    {'name': 'Old',    'description': '', 'lastUpdated': 100},
        'newest': {'name': 'Newest', 'description': '', 'lastUpdated': 999},
        'mid':    {'name': 'Mid',    'description': '', 'lastUpdated': 500},
    })
    out = ai_review._catalog_index()
    assert [e['slug'] for e in out] == ['newest', 'mid', 'old']


def test_catalog_index_empty_when_watcher_unavailable(contrib_ready, monkeypatch):
    from skills import watcher
    def boom():
        raise RuntimeError('watcher not initialised')
    monkeypatch.setattr(watcher, 'get_skills', boom)
    assert ai_review._catalog_index() == []


# ── _compose_prompt ────────────────────────────────────────────────────────


def test_compose_includes_submission_metadata(contrib_ready, monkeypatch):
    _stub_catalog(monkeypatch, {})
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip({'SKILL.md': _minimal_skill_md(name='Hello')}),
        original_filename='ok.zip',
    )
    prompt = ai_review._compose_prompt(sub['id'])
    assert '## Submission' in prompt
    assert f'- id: {sub["id"]}' in prompt
    assert '- slug:' in prompt
    assert '- license: MIT' in prompt


def test_compose_strips_submitter_cookie_name_and_ip(contrib_ready, monkeypatch):
    """Defence-in-depth privacy: prompt must never carry submitter PII."""
    _stub_catalog(monkeypatch, {})
    sub = contributions.create_submission(
        submitter='alice@internal.example',
        submitter_ip='203.0.113.42',
        zip_bytes=_make_zip({'SKILL.md': _minimal_skill_md()}),
        original_filename='private.zip',
    )
    prompt = ai_review._compose_prompt(sub['id'])
    assert 'alice@internal.example' not in prompt
    assert '203.0.113.42' not in prompt
    assert 'private.zip' not in prompt


def test_compose_includes_policy_citation(contrib_ready, monkeypatch):
    _stub_catalog(monkeypatch, {})
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip({'SKILL.md': _minimal_skill_md()}),
        original_filename='ok.zip',
    )
    prompt = ai_review._compose_prompt(sub['id'])
    assert 'docs/SKILL_POLICY.md' in prompt
    assert '## Policy' in prompt


def test_compose_includes_response_schema(contrib_ready, monkeypatch):
    _stub_catalog(monkeypatch, {})
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip({'SKILL.md': _minimal_skill_md()}),
        original_filename='ok.zip',
    )
    prompt = ai_review._compose_prompt(sub['id'])
    assert '## Output schema' in prompt
    assert '"overall"' in prompt
    assert '"findings"' in prompt
    assert 'prompt_injection' in prompt
    assert 'licence' in prompt


def test_compose_truncates_to_max_input_tokens_budget(contrib_ready, monkeypatch, settings):
    settings.AI_REVIEW_MAX_INPUT_TOKENS = 100   # crank way down
    ai_review._config = ai_review._build_config()
    _stub_catalog(monkeypatch, {})

    files = {'SKILL.md': _minimal_skill_md()}
    files['x.py'] = 'y' * 50000
    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip(files), original_filename='ok.zip',
    )
    prompt = ai_review._compose_prompt(sub['id'])
    # 100 tokens × 4 chars/token = 400 chars + trailing marker.
    assert len(prompt) <= (100 * 4) + 80
    assert '…(prompt truncated' in prompt
