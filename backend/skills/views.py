import os

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from .classifier import get_categories
from .file_reader import read_skill_files
from .zipper import create_zip_response
from .watcher import get_skills
from .parser import parse_skill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _install_paths(skill_name):
    return {
        'claudeCode': f'~/.claude/skills/{skill_name}',
        'opencode': f'~/.opencode/skills/{skill_name}',
    }


def _skill_dir(skill_name):
    return os.path.join(settings.SKILL_REPO_PATH, skill_name)


def _version_dir(skill_name, version):
    """Return the directory for a skill version (or None if invalid)."""
    skill_dir_path = _skill_dir(skill_name)
    if version == 'original':
        # 'original' is only valid when the skill has versions
        skill = get_skills().get(skill_name)
        if skill is None or not skill.get('versions'):
            return None
        return skill_dir_path
    else:
        path = os.path.join(skill_dir_path, version)
        return path if os.path.isdir(path) else None


def _search_sort_key(skill, search):
    name = skill.get('name', '').lower()
    if search.lower() in name:
        return 0
    return 1


# ---------------------------------------------------------------------------
# HTML shells — return the static frontend HTML as-is (no templating)
# ---------------------------------------------------------------------------

def _read_shell(filename):
    path = settings.FRONTEND_DIR / filename
    with open(path, 'rb') as f:
        return HttpResponse(f.read(), content_type='text/html; charset=utf-8')


@require_GET
def index_shell(request):
    return _read_shell('index.html')


@require_GET
def skill_shell(request, name):
    # The shell is served regardless of whether <name> exists; the frontend
    # calls /api/skills/<name> and shows an inline "not found" state on 404.
    return _read_shell('skill.html')


# ---------------------------------------------------------------------------
# JSON API views
# ---------------------------------------------------------------------------

@require_GET
def api_health(request):
    skills = get_skills()
    return JsonResponse({
        'status': 'ok',
        'environment': 'production' if not settings.DEBUG else 'development',
        'skillCount': len(skills),
    })


@require_GET
def api_skill_list(request):
    search = request.GET.get('search', '').strip()
    category = request.GET.get('category', '').strip()

    skills = list(get_skills().values())

    # Filter by category
    if category and category != 'All':
        skills = [s for s in skills if s.get('category') == category]

    # Filter by search
    if search:
        q = search.lower()
        skills = [
            s for s in skills
            if q in s.get('name', '').lower() or q in s.get('description', '').lower()
        ]
        skills.sort(key=lambda s: _search_sort_key(s, search))

    # Strip content from list response
    result = []
    for s in skills:
        item = {k: v for k, v in s.items() if k != 'content'}
        result.append(item)

    return JsonResponse({
        'skills': result,
        'categories': get_categories(),
    })


@require_GET
def api_skill_detail(request, name):
    skill = get_skills().get(name)
    if skill is None:
        return JsonResponse({'error': f"Skill '{name}' not found"}, status=404)

    data = dict(skill)
    data['installPaths'] = _install_paths(name)
    data['repoPath'] = _skill_dir(name)
    return JsonResponse(data)


@require_GET
def api_skill_zip(request, name):
    skill = get_skills().get(name)
    if skill is None:
        return JsonResponse({'error': f"Skill '{name}' not found"}, status=404)
    return create_zip_response(_skill_dir(name), name)


@require_GET
def api_skill_files(request, name):
    skill = get_skills().get(name)
    if skill is None:
        return JsonResponse({'error': f"Skill '{name}' not found"}, status=404)
    files = read_skill_files(_skill_dir(name))
    return JsonResponse(files, safe=False)


@require_GET
def api_versions(request, name):
    skill = get_skills().get(name)
    if skill is None:
        return JsonResponse({'error': f"Skill '{name}' not found"}, status=404)
    return JsonResponse({
        'skill': name,
        'currentVersion': skill.get('currentVersion'),
        'versions': skill.get('versions', []),
    })


@require_GET
def api_version_detail(request, name, version):
    skill = get_skills().get(name)
    if skill is None:
        return JsonResponse({'error': f"Skill '{name}' not found"}, status=404)

    ver_dir = _version_dir(name, version)
    if ver_dir is None:
        return JsonResponse({'error': f"Version '{version}' not found"}, status=404)

    ver_skill = parse_skill(ver_dir, name) if version == 'original' else _parse_version_dir(ver_dir, name)
    if ver_skill is None:
        return JsonResponse({'error': f"Version '{version}' not found"}, status=404)

    data = dict(ver_skill)
    data['installPaths'] = _install_paths(name)
    data['repoPath'] = ver_dir
    return JsonResponse(data)


@require_GET
def api_version_zip(request, name, version):
    skill = get_skills().get(name)
    if skill is None:
        return JsonResponse({'error': f"Skill '{name}' not found"}, status=404)

    ver_dir = _version_dir(name, version)
    if ver_dir is None:
        return JsonResponse({'error': f"Version '{version}' not found"}, status=404)

    zip_name = f'{name}-{version}'
    return create_zip_response(ver_dir, zip_name)


@require_GET
def api_version_files(request, name, version):
    skill = get_skills().get(name)
    if skill is None:
        return JsonResponse({'error': f"Skill '{name}' not found"}, status=404)

    ver_dir = _version_dir(name, version)
    if ver_dir is None:
        return JsonResponse({'error': f"Version '{version}' not found"}, status=404)

    files = read_skill_files(ver_dir)
    return JsonResponse(files, safe=False)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_version_dir(ver_dir, skill_name):
    """Parse a specific version subdirectory (not the main skill dir)."""
    from .parser import parse_skill_from_dir
    skill = parse_skill_from_dir(ver_dir, skill_name)
    if skill is None:
        return None
    skill['currentVersion'] = None
    skill['versions'] = []
    return skill
