import os
import re
from datetime import datetime, timezone
from pathlib import Path

import frontmatter

from .classifier import classify


def _count_files(dir_path):
    count = 0
    for _, _, files in os.walk(dir_path):
        count += len(files)
    return count


def _last_modified(dir_path):
    latest = 0
    for root, _, files in os.walk(dir_path):
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
    pattern = re.compile(r'^(\d{8})-.+')
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


def parse_skill_from_dir(dir_path, skill_name):
    """Parse SKILL.md from dir_path. Returns dict or None."""
    skill_md = os.path.join(dir_path, 'SKILL.md')
    if not os.path.isfile(skill_md):
        return None

    try:
        post = frontmatter.load(skill_md)
    except Exception:
        return None

    meta = post.metadata
    classification = classify(skill_name, meta)

    return {
        'name': meta.get('name') or skill_name,
        'description': meta.get('description') or '',
        'license': meta.get('license') or 'Unknown',
        'category': classification['category'],
        'icon': classification['icon'],
        'fileCount': _count_files(dir_path),
        'lastUpdated': _last_modified(dir_path),
        'content': post.content,
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
        skill['versions'] = [
            {'version': v['version'], 'date': v['date']} for v in versions
        ] + [{'version': 'original', 'date': None}]
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
