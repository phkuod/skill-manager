const CATEGORY_MAP = {
  // Development
  'frontend-design': { category: 'Development', icon: '🎨' },
  'web-artifacts-builder': { category: 'Development', icon: '🌐' },
  'mcp-builder': { category: 'Development', icon: '🔧' },
  'skill-creator': { category: 'Development', icon: '⚡' },

  // Content
  'doc-coauthoring': { category: 'Content', icon: '📝' },
  'internal-comms': { category: 'Content', icon: '📢' },
  'brand-guidelines': { category: 'Content', icon: '🏷️' },
  'slack-gif-creator': { category: 'Content', icon: '🎬' },

  // Tools
  'pdf': { category: 'Tools', icon: '📄' },
  'docx': { category: 'Tools', icon: '📃' },
  'pptx': { category: 'Tools', icon: '📊' },
  'xlsx': { category: 'Tools', icon: '📈' },
  'canvas-design': { category: 'Tools', icon: '🖼️' },
  'theme-factory': { category: 'Tools', icon: '🎭' },

  // Data & AI
  'claude-api': { category: 'Data & AI', icon: '🤖' },
  'algorithmic-art': { category: 'Data & AI', icon: '🎆' },

  // Testing
  'webapp-testing': { category: 'Testing', icon: '🧪' },
};

const DEFAULT = { category: 'Other', icon: '📦' };

export function classify(skillName) {
  return CATEGORY_MAP[skillName] || DEFAULT;
}

export function getCategories() {
  const categories = new Set();
  for (const entry of Object.values(CATEGORY_MAP)) {
    categories.add(entry.category);
  }
  return ['All', ...Array.from(categories).sort()];
}
