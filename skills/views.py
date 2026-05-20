import json
import os
from datetime import datetime, timezone

from django.conf import settings
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

# (from .classifier import get_categories) - removed dependency
from . import usage
from .file_reader import read_skill_files
from .installer import install_skill, InstallError, uninstall_skill
from .inventory import list_installed_skills, InventoryError
from .middleware import get_client_ip
from .parser import parse_skill, parse_skill_from_dir
from .zipper import create_zip_response
from .watcher import get_skills





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
    """Return the directory for a skill version, or None if invalid.

    Validates `version` against the parsed catalog before any FS access so
    a request like /api/skills/<n>/versions/../files cannot walk above the
    skill directory and leak the whole skill repo.
    """
    skill = get_skills().get(skill_name)
    if skill is None:
        return None

    valid_versions = {v['version'] for v in skill.get('versions', [])}
    if version not in valid_versions:
        return None

    skill_dir_path = _skill_dir(skill_name)
    if version == 'original':
        return skill_dir_path

    path = os.path.join(skill_dir_path, version)
    # Defense-in-depth: confirm the resolved path is strictly inside the
    # configured skill repo root, in case the catalog ever drifts.
    try:
        repo_root = os.path.realpath(settings.SKILL_REPO_PATH)
        resolved = os.path.realpath(path)
        if (os.path.commonpath([resolved, repo_root]) != repo_root
                or resolved == repo_root):
            return None
    except (ValueError, OSError):
        return None

    return path if os.path.isdir(path) else None


def _search_sort_key(skill, search):
    """Rank skills by where the query hit: name > description > content."""
    q = search.lower()
    if q in skill.get('name', '').lower():
        return 0
    if q in skill.get('description', '').lower():
        return 1
    return 2


# Fields surfaced in the catalog list view. Anything beyond this set
# (notably `contentHtml`, ~5 KB of rendered markdown per skill, and
# `license`) is stripped before responses leave this layer.
_LIST_FIELDS = (
    'name', 'icon', 'description', 'fileCount', 'lastUpdated',
    'content', 'currentVersion', 'versions',
)


def _summary(skill):
    """Project a parsed skill dict to the list-view field set."""
    return {field: skill.get(field) for field in _LIST_FIELDS}


_DEFAULT_PAGE_LIMIT = 50
_MAX_PAGE_LIMIT = 200


def _get_int_param(request, name, default, minimum=1, maximum=None):
    """Parse a positive integer query param. Falls back to default on bad input,
    caps at maximum when provided."""
    raw = request.GET.get(name)
    if raw is None or raw == '':
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if value < minimum:
        return default
    if maximum is not None and value > maximum:
        return maximum
    return value


@require_GET
def home(request):
    skills_dict = get_skills()
    skills = [_summary(s) for s in skills_dict.values()]
    return render(request, 'skills/home.html', {
        'skills': skills,
    })


@require_GET
def skill_detail(request, name):
    skill = get_skills().get(name)
    if skill is None:
        raise Http404(f"Skill '{name}' not found")
    # For multi-version skills redirect to the latest version URL so the
    # version context is available to the JS layer (file fetching, etc.).
    current = skill.get('currentVersion')
    if current:
        return redirect('skill_detail_version', name=name, version=current)
    return render(request, 'skills/skill_detail.html', {
        'skill': skill,
        'skill_name': name,
        'install_paths': _install_paths(name),
        'version': None,
    })


@require_GET
def skill_detail_version(request, name, version):
    skill = get_skills().get(name)
    if skill is None:
        raise Http404(f"Skill '{name}' not found")
    ver_dir = _version_dir(name, version)
    if ver_dir is None:
        raise Http404(f"Version '{version}' not found")
    if version == 'original':
        ver_skill = parse_skill(ver_dir, name)
    else:
        ver_skill = _parse_version_dir(ver_dir, name)
    if ver_skill is None:
        raise Http404(f"Version '{version}' not found")
    # Preserve parent skill's version list and metadata so the UI stays consistent
    ver_skill['versions'] = skill.get('versions', [])
    ver_skill['currentVersion'] = skill.get('currentVersion')
    
    # Fallback to main skill metadata if versioned metadata is missing
    for key in ['name', 'description', 'icon']:
        if not ver_skill.get(key) and skill.get(key):
            ver_skill[key] = skill[key]
    return render(request, 'skills/skill_detail.html', {
        'skill': ver_skill,
        'skill_name': name,
        'install_paths': _install_paths(name),
        'version': version,
    })


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
def api_version(request):
    # Discovery endpoint at /api/version. Top-level (not v1-prefixed) so
    # clients can discover supported API versions before choosing a path.
    return JsonResponse({
        'app': 'skill-market',
        'apiVersions': ['v1'],
    })


@require_GET
def api_skill_list(request):
    search = request.GET.get('search', '').strip()
    page = _get_int_param(request, 'page', default=1, minimum=1)
    limit = _get_int_param(
        request, 'limit',
        default=_DEFAULT_PAGE_LIMIT,
        minimum=1,
        maximum=_MAX_PAGE_LIMIT,
    )

    skills = list(get_skills().values())

    # Filter by search — match name, description, or markdown body. Search
    # runs against the full skill dicts (so `content` is matched) before we
    # project to the list-view field set.
    if search:
        q = search.lower()
        skills = [
            s for s in skills
            if q in s.get('name', '').lower()
            or q in s.get('description', '').lower()
            or q in (s.get('content') or '').lower()
        ]
        skills.sort(key=lambda s: _search_sort_key(s, search))

    total = len(skills)
    start = (page - 1) * limit
    end = start + limit
    page_slice = skills[start:end]
    has_next = end < total

    response = JsonResponse({
        'skills': [_summary(s) for s in page_slice],
        'page': page,
        'limit': limit,
        'total': total,
        'hasNext': has_next,
    })
    if has_next:
        next_qs = request.GET.copy()
        next_qs['page'] = str(page + 1)
        response['Link'] = f'<{request.path}?{next_qs.urlencode()}>; rel="next"'
    return response


@require_GET
def api_skill_detail(request, name):
    skill = get_skills().get(name)
    if skill is None:
        return JsonResponse({'error': f"Skill '{name}' not found"}, status=404)

    data = dict(skill)
    data['installPaths'] = _install_paths(name)
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
    # For multi-version skills, read from the latest version subdirectory.
    current = skill.get('currentVersion')
    if current:
        ver_dir = _version_dir(name, current)
        if ver_dir:
            files = read_skill_files(ver_dir)
            return JsonResponse(files, safe=False)
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


@require_GET
def api_install_targets(request):
    targets = [
        {'name': name, 'base': cfg.get('base', '')}
        for name, cfg in settings.INSTALL_TARGETS.items()
    ]
    return JsonResponse({'targets': targets})


def _do_install(request, src_dir, skill_name):
    """Shared body for both install endpoints. Returns JsonResponse.

    skill_name is the canonical skill identifier from the URL — passed through
    to install_skill so versioned installs land at /<base>/<skill_name>/
    rather than /<base>/<dated-subdir>/.
    """
    user_name = (request.COOKIES.get('CURRENT_USER_NAME') or '').strip()
    if not user_name:
        return JsonResponse(
            {'error': 'Missing or invalid CURRENT_USER_NAME cookie'},
            status=400,
        )

    try:
        payload = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    target = (payload.get('target') or '').strip() if isinstance(payload, dict) else ''
    if not target:
        return JsonResponse({'error': "Missing 'target' in body"}, status=400)

    ip = get_client_ip(request) or None
    try:
        result = install_skill(src_dir, target, user_name, skill_name=skill_name)
    except InstallError as e:
        usage.record_event(
            'install',
            skill=skill_name,
            target=target,
            user=user_name,
            status=e.http_status,
            extra={'error': str(e)[:200]},
            ip=ip,
        )
        return JsonResponse({'error': str(e)}, status=e.http_status)

    usage.record_event(
        'install',
        skill=skill_name,
        target=target,
        user=user_name,
        status=200,
        ip=ip,
    )
    return JsonResponse({'status': 'ok', **result})


@require_POST
def api_skill_install(request, name):
    skill = get_skills().get(name)
    if skill is None:
        return JsonResponse({'error': f"Skill '{name}' not found"}, status=404)
    return _do_install(request, _skill_dir(name), name)


@require_POST
def api_version_install(request, name, version):
    skill = get_skills().get(name)
    if skill is None:
        return JsonResponse({'error': f"Skill '{name}' not found"}, status=404)
    ver_dir = _version_dir(name, version)
    if ver_dir is None:
        return JsonResponse({'error': f"Version '{version}' not found"}, status=404)
    return _do_install(request, ver_dir, name)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_version_dir(ver_dir, skill_name):
    """Parse a specific version subdirectory (not the main skill dir)."""
    skill = parse_skill_from_dir(ver_dir, skill_name)
    if skill is None:
        return None
    skill['currentVersion'] = None
    skill['versions'] = []
    return skill


# ---------------------------------------------------------------------------
# Installed page + uninstall
# ---------------------------------------------------------------------------

def installed_page(request):
    """Render the installed-skills management page.

    Targets and the current user are passed to the template so the JS
    bootstrap can render section headers without an extra round trip.
    """
    user_name = (request.COOKIES.get('CURRENT_USER_NAME') or '').strip()
    targets = [
        {'name': name, 'type': cfg.get('type', ''), 'base': cfg.get('base', ''), 'host': cfg.get('host', '')}
        for name, cfg in settings.INSTALL_TARGETS.items()
    ]
    return render(request, 'skills/installed.html', {
        'user_name': user_name,
        'targets': targets,
        'targets_json': json.dumps(targets),
    })


@require_GET
def api_installed_list(request, target_name):
    user_name = (request.COOKIES.get('CURRENT_USER_NAME') or '').strip()
    if not user_name:
        return JsonResponse(
            {'error': 'Missing or invalid CURRENT_USER_NAME cookie'},
            status=400,
        )
    try:
        result = list_installed_skills(target_name, user_name)
    except InventoryError as exc:
        return JsonResponse({'error': str(exc)}, status=exc.http_status)
    return JsonResponse(result)


def _do_uninstall(request, target_name, name):
    user_name = (request.COOKIES.get('CURRENT_USER_NAME') or '').strip()
    if not user_name:
        return JsonResponse(
            {'error': 'Missing or invalid CURRENT_USER_NAME cookie'},
            status=400,
        )
    ip = get_client_ip(request) or None
    try:
        result = uninstall_skill(target_name, user_name, name)
    except InstallError as exc:
        usage.record_event(
            'uninstall',
            skill=name,
            target=target_name,
            user=user_name,
            status=exc.http_status,
            extra={'error': str(exc)[:200]},
            ip=ip,
        )
        return JsonResponse({'error': str(exc)}, status=exc.http_status)
    usage.record_event(
        'uninstall',
        skill=name,
        target=target_name,
        user=user_name,
        status=200,
        ip=ip,
    )
    return JsonResponse({'status': 'ok', **result})


@require_POST
def api_installed_uninstall(request, target_name, name):
    return _do_uninstall(request, target_name, name)


# ---------------------------------------------------------------------------
# Usage dashboard (admin-gated)
# ---------------------------------------------------------------------------

_USAGE_RANGES = {
    '24h': 24 * 60 * 60,
    '7d': 7 * 24 * 60 * 60,
    '30d': 30 * 24 * 60 * 60,
    '90d': 90 * 24 * 60 * 60,
}
_USAGE_DEFAULT_RANGE = '7d'
_USAGE_RECENT_PAGE_SIZE = 50
_USAGE_RECENT_PAGE_SIZES = (25, 50, 100, 200)


def _usage_recent_page(request) -> int:
    raw = (request.GET.get('page') or '1').strip()
    try:
        page = int(raw)
    except ValueError:
        page = 1
    return max(1, page)


def _usage_recent_page_size(request) -> int:
    raw = (request.GET.get('per_page') or '').strip()
    try:
        size = int(raw)
    except ValueError:
        size = _USAGE_RECENT_PAGE_SIZE
    if size not in _USAGE_RECENT_PAGE_SIZES:
        size = _USAGE_RECENT_PAGE_SIZE
    return size


def _require_usage_admin(request):
    """Allowlist check against USAGE_ADMIN_USERS (CURRENT_USER_NAME cookie).

    Returns the user name when authorised, or an HttpResponseForbidden
    when not. Empty allowlist ⇒ forbidden for everyone (fail closed).
    """
    user = (request.COOKIES.get('CURRENT_USER_NAME') or '').strip()
    admins = getattr(settings, 'USAGE_ADMIN_USERS', set()) or set()
    if not user or user not in admins:
        return HttpResponseForbidden('Forbidden')
    return user


def _usage_range_seconds(request):
    raw = (request.GET.get('range') or _USAGE_DEFAULT_RANGE).strip()
    if raw not in _USAGE_RANGES:
        raw = _USAGE_DEFAULT_RANGE
    return raw, _USAGE_RANGES[raw]


@require_GET
def usage_page(request):
    gate = _require_usage_admin(request)
    if isinstance(gate, HttpResponseForbidden):
        return gate
    range_key, range_seconds = _usage_range_seconds(request)
    summary = usage.query_summary(range_seconds)
    installs = usage.query_installs(range_seconds, group_by='skill')
    pageviews = usage.query_pageviews(range_seconds)
    health = usage.query_health(range_seconds)

    page = _usage_recent_page(request)
    page_size = _usage_recent_page_size(request)
    recent_result = usage.query_recent(limit=page_size, offset=(page - 1) * page_size)
    recent_rows = recent_result['rows']
    recent_total = recent_result['total']
    total_pages = max(1, (recent_total + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages
        recent_result = usage.query_recent(limit=page_size, offset=(page - 1) * page_size)
        recent_rows = recent_result['rows']
    for e in recent_rows:
        ts = e.get('ts')
        if ts:
            e['ts'] = datetime.fromtimestamp(ts, tz=timezone.utc)

    return render(request, 'skills/usage.html', {
        'user_name': gate,
        'range_key': range_key,
        'range_options': list(_USAGE_RANGES.keys()),
        'summary': summary,
        'installs': installs,
        'pageviews': pageviews,
        'health': health,
        'recent': recent_rows,
        'recent_page': page,
        'recent_page_size': page_size,
        'recent_page_size_options': list(_USAGE_RECENT_PAGE_SIZES),
        'recent_total': recent_total,
        'recent_total_pages': total_pages,
        'recent_has_prev': page > 1,
        'recent_has_next': page < total_pages,
        'recent_prev_page': page - 1,
        'recent_next_page': page + 1,
        'recent_start': 0 if recent_total == 0 else (page - 1) * page_size + 1,
        'recent_end': min(page * page_size, recent_total),
    })


@require_GET
def api_usage_summary(request):
    gate = _require_usage_admin(request)
    if isinstance(gate, HttpResponseForbidden):
        return gate
    range_key, range_seconds = _usage_range_seconds(request)
    data = usage.query_summary(range_seconds)
    data['range'] = range_key
    return JsonResponse(data)


@require_GET
def api_usage_installs(request):
    gate = _require_usage_admin(request)
    if isinstance(gate, HttpResponseForbidden):
        return gate
    range_key, range_seconds = _usage_range_seconds(request)
    group_by = (request.GET.get('group') or 'skill').strip()
    if group_by not in ('skill', 'target', 'day'):
        group_by = 'skill'
    data = usage.query_installs(range_seconds, group_by=group_by)
    data['range'] = range_key
    return JsonResponse(data)


@require_GET
def api_usage_pageviews(request):
    gate = _require_usage_admin(request)
    if isinstance(gate, HttpResponseForbidden):
        return gate
    range_key, range_seconds = _usage_range_seconds(request)
    data = usage.query_pageviews(range_seconds)
    data['range'] = range_key
    return JsonResponse(data)


@require_GET
def api_usage_health(request):
    gate = _require_usage_admin(request)
    if isinstance(gate, HttpResponseForbidden):
        return gate
    range_key, range_seconds = _usage_range_seconds(request)
    data = usage.query_health(range_seconds)
    data['range'] = range_key
    return JsonResponse(data)
