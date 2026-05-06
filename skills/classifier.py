CATEGORY_MAP = {
    # Development
    'frontend-design':      {'category': 'Development', 'icon': '🎨'},
    'web-artifacts-builder': {'category': 'Development', 'icon': '🌐'},
    'mcp-builder':          {'category': 'Development', 'icon': '🔧'},
    'skill-creator':        {'category': 'Development', 'icon': '⚡'},

    # Content
    'doc-coauthoring':      {'category': 'Content', 'icon': '📝'},
    'internal-comms':       {'category': 'Content', 'icon': '📢'},
    'brand-guidelines':     {'category': 'Content', 'icon': '🏷️'},
    'slack-gif-creator':    {'category': 'Content', 'icon': '🎬'},

    # Tools
    'pdf':                  {'category': 'Tools', 'icon': '📄'},
    'docx':                 {'category': 'Tools', 'icon': '📃'},
    'pptx':                 {'category': 'Tools', 'icon': '📊'},
    'xlsx':                 {'category': 'Tools', 'icon': '📈'},
    'canvas-design':        {'category': 'Tools', 'icon': '🖼️'},
    'theme-factory':        {'category': 'Tools', 'icon': '🎭'},

    # Data & AI
    'claude-api':           {'category': 'Data & AI', 'icon': '🤖'},
    'algorithmic-art':      {'category': 'Data & AI', 'icon': '🎆'},

    # Testing
    'webapp-testing':       {'category': 'Testing', 'icon': '🧪'},
}

DEFAULT = {'category': 'Other', 'icon': '📦'}


def classify(skill_name, meta=None):
    """Resolve category/icon for a skill.

    Priority:
      1. `category` / `icon` from SKILL.md frontmatter (`meta`)
      2. CATEGORY_MAP keyed by skill name
      3. DEFAULT ('Other' / 📦)

    Each field is resolved independently — a skill can specify only `category`
    in frontmatter and still inherit the icon from CATEGORY_MAP.
    """
    fallback = CATEGORY_MAP.get(skill_name, DEFAULT)
    if not meta:
        return dict(fallback)
    return {
        'category': meta.get('category') or fallback['category'],
        'icon': meta.get('icon') or fallback['icon'],
    }


def get_categories(skills=None):
    """Return ['All', ...sorted unique categories].

    Always includes categories defined in CATEGORY_MAP. When `skills` is
    provided, also includes any category observed on a live skill (so a new
    `category:` value in SKILL.md frontmatter shows up as a filter without
    a code change). 'Other' is excluded — it's the catch-all bucket.
    """
    cats = set(entry['category'] for entry in CATEGORY_MAP.values())
    if skills:
        for s in skills.values():
            c = s.get('category')
            if c:
                cats.add(c)
    cats.discard('Other')
    return ['All'] + sorted(cats)
