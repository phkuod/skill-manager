"""Dev seeder for the /installed/ page.

Populates each `local` install target in settings.INSTALL_TARGETS with a
small, fixed set of catalog skills (different per target) plus one orphan
directory so both subsections in the UI ("In catalog" / "Not in catalog")
have content.

Usage:
    venv/Scripts/python.exe scripts/seed-installed-dev.py            # seed
    venv/Scripts/python.exe scripts/seed-installed-dev.py --clean    # remove
    DEV_USER_NAME=alice venv/Scripts/python.exe scripts/seed-installed-dev.py

The user_name is read from the DEV_USER_NAME env var (default 'dev') and
must match the CURRENT_USER_NAME browser cookie for the page to surface
the seeded directories. Set the cookie in DevTools:
    Application -> Cookies -> http://127.0.0.1:3000 -> CURRENT_USER_NAME = dev

Idempotent: running twice without --clean is safe (existing skill dirs
are overwritten).
"""
import argparse
import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skill_market.settings')

# Load .env.development if present so install targets populate when the
# seeder is run outside start.sh.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, '.env.development'))
except ImportError:
    pass

import django  # noqa: E402
django.setup()

from django.conf import settings  # noqa: E402

# Which catalog skills to copy into each target. Keep these short and
# distinct so the UI shows variety across F12 / F15 / F20.
SEED_PLAN = {
    'F12': ['pdf', 'docx', 'xlsx'],
    'F15': ['claude-api', 'mcp-builder'],
    'F20': ['frontend-design', 'theme-factory', 'canvas-design'],
}

# An orphan dir is dropped only in F12 so the "Not in catalog" subsection
# is exercised. Its name is intentionally NOT in the catalog.
ORPHAN_NAME = 'legacy-skill-v0'


def _expand_base(target_cfg, user_name):
    base = target_cfg.get('base', '')
    return base.format(user_name=user_name).rstrip('/\\')


def seed(user_name):
    skill_repo = settings.SKILL_REPO_PATH
    if not os.path.isdir(skill_repo):
        sys.exit(f'SKILL_REPO_PATH not found: {skill_repo}')

    for target_name, cfg in settings.INSTALL_TARGETS.items():
        if cfg.get('type') != 'local':
            print(f'[skip] {target_name}: type={cfg.get("type")} (only local supported by seeder)')
            continue
        if target_name not in SEED_PLAN:
            print(f'[skip] {target_name}: no entry in SEED_PLAN')
            continue

        base = _expand_base(cfg, user_name)
        os.makedirs(base, exist_ok=True)

        for skill_name in SEED_PLAN[target_name]:
            src = os.path.join(skill_repo, skill_name)
            if not os.path.isdir(src):
                print(f'[warn] {target_name}: source missing — {src}')
                continue
            dst = os.path.join(base, skill_name)
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f'[seed] {target_name}: {skill_name} -> {dst}')

        if target_name == 'F12':
            orphan_dir = os.path.join(base, ORPHAN_NAME)
            os.makedirs(orphan_dir, exist_ok=True)
            with open(os.path.join(orphan_dir, 'README.txt'), 'w') as f:
                f.write('Seeded orphan - not in catalog. Safe to delete.\n')
            print(f'[seed] {target_name}: orphan {ORPHAN_NAME} -> {orphan_dir}')

    print(f"\nDone. Set the cookie CURRENT_USER_NAME='{user_name}' and visit /installed/.")


def clean(user_name):
    for target_name, cfg in settings.INSTALL_TARGETS.items():
        if cfg.get('type') != 'local':
            continue
        base = _expand_base(cfg, user_name)
        if not os.path.isdir(base):
            print(f'[skip] {target_name}: {base} does not exist')
            continue
        names = SEED_PLAN.get(target_name, []) + ([ORPHAN_NAME] if target_name == 'F12' else [])
        for name in names:
            path = os.path.join(base, name)
            if os.path.isdir(path):
                shutil.rmtree(path)
                print(f'[clean] {target_name}: removed {path}')
    print('\nDone cleaning.')


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--clean', action='store_true',
                        help='Remove seeded dirs instead of creating them.')
    parser.add_argument('--user', default=os.environ.get('DEV_USER_NAME', 'dev'),
                        help='user_name to expand into base templates (default: $DEV_USER_NAME or "dev")')
    args = parser.parse_args()

    if not settings.INSTALL_TARGETS:
        sys.exit('settings.INSTALL_TARGETS is empty — is .env.development sourced?')

    print(f'user_name = {args.user!r}')
    print(f'targets   = {sorted(settings.INSTALL_TARGETS.keys())}')
    print()

    if args.clean:
        clean(args.user)
    else:
        seed(args.user)


if __name__ == '__main__':
    main()
