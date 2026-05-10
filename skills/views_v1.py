"""v1 API surface — wraps responses in the {data, meta?, error?} envelope.

The legacy /api/* paths in views.py keep their pre-existing shape for
backward compatibility. New clients should target /api/v1/* and key off
the structured `error.code` rather than the HTTP status when retrying
or branching.

Most v1 handlers reuse private helpers from views.py (path validation,
search ranking, list projection, pagination params) — only the response
shaping differs.
"""
import json

from django.conf import settings
from django.views.decorators.http import require_GET, require_POST

from . import envelope as e
from .file_reader import read_skill_files
from .installer import install_skill, InstallError
from .parser import parse_skill
from .views import (
    _DEFAULT_PAGE_LIMIT,
    _MAX_PAGE_LIMIT,
    _get_int_param,
    _install_paths,
    _parse_version_dir,
    _search_sort_key,
    _skill_dir,
    _summary,
    _version_dir,
)
from .watcher import get_skills
from .zipper import create_zip_response


# ---------------------------------------------------------------------------
# Lookup helpers — return (value, None) on hit, (None, err_response) on miss
# ---------------------------------------------------------------------------

def _skill_or_err(name):
    skill = get_skills().get(name)
    if skill is None:
        return None, e.err(e.SKILL_NOT_FOUND, f"Skill '{name}' not found", status=404)
    return skill, None


def _version_dir_or_err(name, version):
    ver_dir = _version_dir(name, version)
    if ver_dir is None:
        return None, e.err(e.VERSION_NOT_FOUND, f"Version '{version}' not found", status=404)
    return ver_dir, None


# ---------------------------------------------------------------------------
# v1 endpoints
# ---------------------------------------------------------------------------

@require_GET
def api_v1_health(request):
    skills = get_skills()
    return e.ok({
        'status': 'ok',
        'environment': 'production' if not settings.DEBUG else 'development',
        'skillCount': len(skills),
    })


@require_GET
def api_v1_install_targets(request):
    targets = [
        {'name': name, 'base': cfg.get('base', '')}
        for name, cfg in settings.INSTALL_TARGETS.items()
    ]
    return e.ok({'targets': targets})


@require_GET
def api_v1_skill_list(request):
    search = request.GET.get('search', '').strip()
    page = _get_int_param(request, 'page', default=1, minimum=1)
    limit = _get_int_param(
        request, 'limit',
        default=_DEFAULT_PAGE_LIMIT,
        minimum=1,
        maximum=_MAX_PAGE_LIMIT,
    )

    skills = list(get_skills().values())

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

    response = e.ok(
        [_summary(s) for s in page_slice],
        meta={
            'page': page,
            'limit': limit,
            'total': total,
            'hasNext': has_next,
        },
    )
    if has_next:
        next_qs = request.GET.copy()
        next_qs['page'] = str(page + 1)
        response['Link'] = f'<{request.path}?{next_qs.urlencode()}>; rel="next"'
    return response


@require_GET
def api_v1_skill_detail(request, name):
    skill, err_resp = _skill_or_err(name)
    if err_resp:
        return err_resp
    data = dict(skill)
    data['installPaths'] = _install_paths(name)
    data['repoPath'] = _skill_dir(name)
    return e.ok(data)


@require_GET
def api_v1_skill_zip(request, name):
    _, err_resp = _skill_or_err(name)
    if err_resp:
        return err_resp
    return create_zip_response(_skill_dir(name), name)


@require_GET
def api_v1_skill_files(request, name):
    skill, err_resp = _skill_or_err(name)
    if err_resp:
        return err_resp
    current = skill.get('currentVersion')
    if current:
        ver_dir = _version_dir(name, current)
        if ver_dir:
            return e.ok(read_skill_files(ver_dir))
    return e.ok(read_skill_files(_skill_dir(name)))


@require_GET
def api_v1_versions(request, name):
    skill, err_resp = _skill_or_err(name)
    if err_resp:
        return err_resp
    return e.ok({
        'skill': name,
        'currentVersion': skill.get('currentVersion'),
        'versions': skill.get('versions', []),
    })


@require_GET
def api_v1_version_detail(request, name, version):
    _, err_resp = _skill_or_err(name)
    if err_resp:
        return err_resp
    ver_dir, err_resp = _version_dir_or_err(name, version)
    if err_resp:
        return err_resp

    ver_skill = parse_skill(ver_dir, name) if version == 'original' else _parse_version_dir(ver_dir, name)
    if ver_skill is None:
        return e.err(e.VERSION_NOT_FOUND, f"Version '{version}' not found", status=404)
    data = dict(ver_skill)
    data['installPaths'] = _install_paths(name)
    data['repoPath'] = ver_dir
    return e.ok(data)


@require_GET
def api_v1_version_zip(request, name, version):
    _, err_resp = _skill_or_err(name)
    if err_resp:
        return err_resp
    ver_dir, err_resp = _version_dir_or_err(name, version)
    if err_resp:
        return err_resp
    return create_zip_response(ver_dir, f'{name}-{version}')


@require_GET
def api_v1_version_files(request, name, version):
    _, err_resp = _skill_or_err(name)
    if err_resp:
        return err_resp
    ver_dir, err_resp = _version_dir_or_err(name, version)
    if err_resp:
        return err_resp
    return e.ok(read_skill_files(ver_dir))


def _do_install_v1(request, src_dir, skill_name):
    user_name = (request.COOKIES.get('CURRENT_USER_NAME') or '').strip()
    if not user_name:
        return e.err(
            e.INSTALL_USERNAME_INVALID,
            'Missing or invalid CURRENT_USER_NAME cookie',
            status=400,
        )

    try:
        payload = json.loads(request.body or b'{}')
    except ValueError:
        return e.err(e.INVALID_BODY, 'Invalid JSON body', status=400)

    if not isinstance(payload, dict):
        return e.err(e.INVALID_BODY, 'Body must be a JSON object', status=400)

    target = (payload.get('target') or '').strip()
    if not target:
        return e.err(e.INVALID_BODY, "Missing 'target' in body", status=400)

    try:
        result = install_skill(src_dir, target, user_name, skill_name=skill_name)
    except InstallError as exc:
        return e.err(exc.code, str(exc), status=exc.http_status)

    return e.ok(result)


@require_POST
def api_v1_skill_install(request, name):
    _, err_resp = _skill_or_err(name)
    if err_resp:
        return err_resp
    return _do_install_v1(request, _skill_dir(name), name)


@require_POST
def api_v1_version_install(request, name, version):
    _, err_resp = _skill_or_err(name)
    if err_resp:
        return err_resp
    ver_dir, err_resp = _version_dir_or_err(name, version)
    if err_resp:
        return err_resp
    return _do_install_v1(request, ver_dir, name)
