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


def classify(skill_name):
    return CATEGORY_MAP.get(skill_name, DEFAULT)


def get_categories():
    cats = sorted(set(entry['category'] for entry in CATEGORY_MAP.values()))
    return ['All'] + cats
