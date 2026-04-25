import os

MAX_FILE_SIZE = 500 * 1024  # 500 KB
BINARY_CHECK_BYTES = 8192

LANGUAGE_MAP = {
    '.md':   'markdown',
    '.py':   'python',
    '.ts':   'typescript',
    '.tsx':  'typescript',
    '.js':   'javascript',
    '.jsx':  'javascript',
    '.go':   'go',
    '.rb':   'ruby',
    '.java': 'java',
    '.cs':   'csharp',
    '.php':  'php',
    '.sh':   'bash',
    '.json': 'json',
    '.yaml': 'yaml',
    '.yml':  'yaml',
}


def infer_language(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    return LANGUAGE_MAP.get(ext, 'text')


def _is_binary(path):
    try:
        with open(path, 'rb') as f:
            chunk = f.read(BINARY_CHECK_BYTES)
        return b'\x00' in chunk
    except OSError:
        return True


def read_skill_files(dir_path, include_content=True):
    """Read all text files in dir_path recursively.

    Returns list of dicts sorted with SKILL.md first.

    With include_content=True (default): each entry is
        {path, language, content, truncated?}
    With include_content=False: each entry is
        {path, language, size, truncated?}  (content is omitted entirely;
        the detail page fetches bodies lazily via read_one_file)."""
    if not os.path.isdir(dir_path):
        return []

    results = []
    for root, dirs, files in os.walk(dir_path):
        dirs.sort()
        for fname in sorted(files):
            abs_path = os.path.join(root, fname)
            rel_path = os.path.relpath(abs_path, dir_path).replace(os.sep, '/')

            if _is_binary(abs_path):
                continue

            try:
                size = os.path.getsize(abs_path)
            except OSError:
                continue

            language = infer_language(fname)
            truncated = size > MAX_FILE_SIZE

            if not include_content:
                entry = {'path': rel_path, 'language': language, 'size': size}
                if truncated:
                    entry['truncated'] = True
                results.append(entry)
                continue

            if truncated:
                results.append({'path': rel_path, 'content': None, 'language': language, 'truncated': True})
                continue

            try:
                with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except OSError:
                continue

            results.append({'path': rel_path, 'content': content, 'language': language})

    # Sort: SKILL.md first, rest alphabetically (already sorted by os.walk + sorted())
    results.sort(key=lambda f: (0 if f['path'] == 'SKILL.md' else 1, f['path']))
    return results


def read_one_file(dir_path, rel_path):
    """Read a single file inside dir_path. Returns dict or None.

    Rejects path traversal: rel_path must resolve to a descendant of dir_path."""
    if not os.path.isdir(dir_path):
        return None

    # Normalize and reject traversal
    safe_rel = rel_path.replace('\\', '/').lstrip('/')
    abs_path = os.path.realpath(os.path.join(dir_path, safe_rel))
    base = os.path.realpath(dir_path)
    if not abs_path.startswith(base + os.sep) and abs_path != base:
        return None
    if not os.path.isfile(abs_path):
        return None
    if _is_binary(abs_path):
        return None

    try:
        size = os.path.getsize(abs_path)
    except OSError:
        return None

    language = infer_language(os.path.basename(abs_path))
    final_rel = os.path.relpath(abs_path, base).replace(os.sep, '/')

    if size > MAX_FILE_SIZE:
        return {'path': final_rel, 'content': None, 'language': language, 'truncated': True}

    try:
        with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except OSError:
        return None

    return {'path': final_rel, 'content': content, 'language': language}
