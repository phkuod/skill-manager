import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import frontmatter
import markdown
import nh3

# (from .classifier import classify) - removed dependency

# Tags and attributes allowed through sanitization.
# Covers everything the markdown renderer produces (fenced_code, tables)
# while blocking dangerous elements like <script>, <iframe>, <object>, etc.
_ALLOWED_TAGS = {
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'br', 'hr',
    'ul', 'ol', 'li',
    'a', 'strong', 'em', 'b', 'i', 'u', 's', 'del', 'ins',
    'code', 'pre', 'blockquote',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'img', 'figure', 'figcaption',
    'dl', 'dt', 'dd',
    'div', 'span', 'sup', 'sub',
}
_ALLOWED_ATTRIBUTES = {
    'a': {'href', 'title', 'target', 'rel'},
    'img': {'src', 'alt', 'title', 'width', 'height'},
    'code': {'class'},
    'pre': {'class'},
    'th': {'align'},
    'td': {'align'},
}

logger = logging.getLogger('skills.parser')


def _count_files(dir_path):
    count = 0
    pattern = re.compile(r'^(\d{8})-.+$')
    for root, dirs, files in os.walk(dir_path):
        if root == dir_path:
            dirs[:] = [d for d in dirs if not (pattern.match(d) and os.path.isfile(os.path.join(dir_path, d, 'SKILL.md')))]
        count += len(files)
    return count


def _last_modified(dir_path):
    latest = 0
    pattern = re.compile(r'^(\d{8})-.+$')
    for root, dirs, files in os.walk(dir_path):
        if root == dir_path:
            dirs[:] = [d for d in dirs if not (pattern.match(d) and os.path.isfile(os.path.join(dir_path, d, 'SKILL.md')))]
        for f in files:
            try:
                mtime = os.stat(os.path.join(root, f)).st_mtime
                if mtime > latest:
                    latest = mtime
            except OSError:
                pass
    if latest == 0:
        try:
            latest = os.stat(dir_path).st_mtime
        except OSError:
            pass
    return datetime.fromtimestamp(latest, tz=timezone.utc).isoformat()


def detect_versions(skill_dir):
    """Return list of {version, path, date} sorted by date descending.
    Only directories matching yyyymmdd-<suffix> that contain a SKILL.md."""
    if not os.path.isdir(skill_dir):
        return []

    versions = []
    pattern = re.compile(r'^(\d{8})-.+$')
    try:
        entries = os.listdir(skill_dir)
    except OSError:
        return []

    for entry in entries:
        m = pattern.match(entry)
        if not m:
            continue
        full_path = os.path.join(skill_dir, entry)
        if not os.path.isdir(full_path):
            continue
        if not os.path.isfile(os.path.join(full_path, 'SKILL.md')):
            continue
        versions.append({
            'version': entry,
            'path': full_path,
            'date': m.group(1),
        })

    versions.sort(key=lambda v: v['date'], reverse=True)
    return versions


def _classify(skill_name, meta):
    """Resolve (icon, category) for a skill from its name keywords.

    An explicit `icon:` in SKILL.md frontmatter overrides only the icon;
    category always derives from the name since frontmatter has no
    category field.
    """
    name_lower = skill_name.lower()
    mapping = (
        (('design', 'art', 'theme', 'css', 'style', 'canvas', 'factory'), '🎨', 'Design'),
        (('tool', 'util', 'convert', 'pdf', 'docx', 'xlsx', 'pptx', 'zip'), '🔧', 'Tools'),
        (('code', 'dev', 'build', 'script', 'api', 'mcp', 'skill'), '💻', 'Code'),
        (('content', 'doc', 'write', 'comms', 'brand', 'internal'), '📝', 'Content'),
        (('test', 'qa', 'check', 'verify'), '🧪', 'Testing'),
        (('ai', 'ml', 'chat', 'claude', 'bot', 'data', 'algorithm'), '🤖', 'AI/ML'),
        (('slack', 'comm', 'message', 'gif'), '💬', 'Communication'),
        (('git', 'repo', 'version'), '📦', 'Other'),
    )
    default_icon, category = '📦', 'Other'
    for keywords, emoji, cat in mapping:
        if any(k in name_lower for k in keywords):
            default_icon, category = emoji, cat
            break

    icon = (meta or {}).get('icon') or default_icon
    return icon, category


def parse_skill_from_dir(dir_path, skill_name):
    """Parse SKILL.md from dir_path. Returns dict or None."""
    skill_md = os.path.join(dir_path, 'SKILL.md')
    if not os.path.isfile(skill_md):
        return None

    try:
        post = frontmatter.load(skill_md)
    except Exception as exc:
        logger.warning('failed to parse %s/SKILL.md: %s', dir_path, exc)
        return None

    meta = post.metadata
    icon, category = _classify(skill_name, meta)

    try:
        raw_html = markdown.markdown(
            post.content,
            extensions=['fenced_code', 'tables'],
        )
        content_html = nh3.clean(
            raw_html,
            tags=_ALLOWED_TAGS,
            attributes=_ALLOWED_ATTRIBUTES,
            link_rel=None,
        )
    except Exception as exc:
        logger.warning('markdown render failed for %s, falling back to empty string: %s', skill_name, exc)
        content_html = ''

    return {
        'name': meta.get('name') or skill_name,
        'description': meta.get('description') or '',
        'license': meta.get('license') or 'Unknown',
        'icon': icon,
        'category': category,
        'fileCount': _count_files(dir_path),
        'lastUpdated': _last_modified(dir_path),
        'content': post.content,
        'contentHtml': content_html,
    }


def parse_skill(skill_dir, skill_name):
    """Parse a skill with version detection. Returns full skill dict or None."""
    if not os.path.isdir(skill_dir):
        return None

    versions = detect_versions(skill_dir)

    if versions:
        # Read content from the latest version dir
        active_dir = versions[0]['path']
        skill = parse_skill_from_dir(active_dir, skill_name)
        if skill is None:
            return None
        skill['currentVersion'] = versions[0]['version']
        versions_list = [{'version': v['version'], 'date': v['date']} for v in versions]
        if os.path.isfile(os.path.join(skill_dir, 'SKILL.md')):
            versions_list.append({'version': 'original', 'date': None})
        skill['versions'] = versions_list
    else:
        skill = parse_skill_from_dir(skill_dir, skill_name)
        if skill is None:
            return None
        skill['currentVersion'] = None
        skill['versions'] = []

    return skill


def parse_all_skills(skill_repo_path):
    """Parse all skills in skill_repo_path. Returns dict {name: skill_dict}."""
    result = {}
    if not os.path.isdir(skill_repo_path):
        return result

    try:
        entries = os.listdir(skill_repo_path)
    except OSError:
        return result

    for entry in sorted(entries):
        full_path = os.path.join(skill_repo_path, entry)
        if not os.path.isdir(full_path):
            continue
        skill = parse_skill(full_path, entry)
        if skill is not None:
            result[entry] = skill

    return result
