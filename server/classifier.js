var CATEGORY_MAP = {
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

var DEFAULT = { category: 'Other', icon: '📦' };

function classify(skillName) {
  return CATEGORY_MAP[skillName] || DEFAULT;
}

function getCategories() {
  var categories = new Set();
  var values = Object.values(CATEGORY_MAP);
  for (var i = 0; i < values.length; i++) {
    categories.add(values[i].category);
  }
  return ['All'].concat(Array.from(categories).sort());
}

module.exports = { classify: classify, getCategories: getCategories };
