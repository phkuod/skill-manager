"""Dev seeder for visually verifying the M4b AI-reviewer UI.

Inserts one contribution submission plus a single ``ai_reviewer`` verdict
comment (rendered by the real ``ai_review._render_comment_body``) into the
running app's submissions DB, so the detail page verdict pill / Re-run
button and the admin-queue AI column have something to render.

Usage:
    AI_REVIEW_ENABLED=true SKILL_REVIEW_ADMINS=dev \
        venv/Scripts/python.exe scripts/seed-ai-review-dev.py

Prints the submission id + the two URLs to open. Set the browser cookie
CURRENT_USER_NAME=dev (matching SKILL_REVIEW_ADMINS) to see the admin
controls. Run against the same env the server uses so both processes
share settings.SUBMISSIONS_DB_PATH.
"""
import io
import os
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skill_market.settings')

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, '.env.development'))
except ImportError:
    pass

import django  # noqa: E402
django.setup()

from django.conf import settings  # noqa: E402
from skills import ai_review, contributions  # noqa: E402


def _make_zip(name):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            'SKILL.md',
            f'---\nname: {name}\ndescription: Seed skill for AI-review UI check.\n'
            f'license: MIT\n---\n# {name}\n\nThis is a seeded contribution.\n',
        )
    return buf.getvalue()


def main():
    contributions.init_submissions(
        settings.SUBMISSIONS_DB_PATH, settings.SUBMISSIONS_BLOB_DIR,
    )

    sub = contributions.create_submission(
        submitter='alice', submitter_ip='127.0.0.1',
        zip_bytes=_make_zip('ai-review-ui-demo'),
        original_filename='ai-review-ui-demo.zip',
    )

    verdict = ai_review._Verdict(
        overall='request_changes',
        confidence=0.97,   # above the 0.8 cap → renders "(capped)"
        summary='Solid skill overall, but a couple of issues should be addressed before publishing.',
        findings=[
            {'severity': 'block', 'title': 'Hardcoded API token in example',
             'detail': 'SKILL.md embeds a real-looking token; replace with a placeholder.'},
            {'severity': 'warn', 'title': 'Overly broad file glob',
             'detail': 'The skill reads **/* which may pick up secrets.'},
            {'severity': 'note', 'title': 'Description could be more specific',
             'detail': 'Mention the concrete trigger conditions.'},
        ],
        model='deepseek/deepseek-r1:free',
        latency_s=6.3,
    )
    contributions.add_comment(
        sub['id'], author=None,
        author_role=contributions.ROLE_AI_REVIEWER,
        body=ai_review._render_comment_body(verdict),
    )

    port = os.environ.get('PORT', '8888')
    base = f'http://127.0.0.1:{port}'
    print(f'seeded submission id={sub["id"]} slug={sub["slug"]}')
    print(f'detail : {base}/contributions/{sub["id"]}/')
    print(f'queue  : {base}/admin/contributions/')


if __name__ == '__main__':
    main()
