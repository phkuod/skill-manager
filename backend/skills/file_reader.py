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


def read_skill_files(dir_path):
    """Read all text files in dir_path recursively.
    Returns list of {path, content, language} sorted with SKILL.md first."""
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

            if size > MAX_FILE_SIZE:
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
