"""Guard for Tailwind bundle regeneration.

Usage: python scripts/tw_regen_check.py OLD_CSS NEW_CSS

Fails (exit 1) if any class token referenced in templates/JS that existed in
the OLD bundle is missing from the NEW bundle — i.e. the regen dropped a
still-used utility.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def referenced_class_tokens():
    tokens = set()
    patterns = ('skills/templates/**/*.html', 'skills/static/skills/js/*.js',
                'skills/static/skills/dev/*.js')
    for pat in patterns:
        for f in ROOT.glob(pat):
            text = f.read_text(encoding='utf-8', errors='ignore')
            for m in re.finditer(r"""class(?:Name)?=["']([^"']+)["']""", text):
                tokens.update(m.group(1).split())
    return {t for t in tokens if t and '{' not in t and '$' not in t}


def css_has(css, cls):
    esc = (cls.replace('\\', '')
              .replace(':', '\\:').replace('/', '\\/').replace('.', '\\.')
              .replace('[', '\\[').replace(']', '\\]').replace('%', '\\%'))
    return ('.' + esc) in css


def main():
    old_css = Path(sys.argv[1]).read_text(encoding='utf-8', errors='ignore')
    new_css = Path(sys.argv[2]).read_text(encoding='utf-8', errors='ignore')
    missing = sorted(t for t in referenced_class_tokens()
                     if css_has(old_css, t) and not css_has(new_css, t))
    if missing:
        print('DROPPED still-referenced utilities:')
        for t in missing:
            print('  ' + t)
        sys.exit(1)
    print('OK: no still-referenced utility dropped.')


if __name__ == '__main__':
    main()
