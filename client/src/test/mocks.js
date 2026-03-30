export const mockSkills = [
  {
    name: 'frontend-design',
    description: 'Create distinctive, production-grade frontend interfaces',
    category: 'Development',
    icon: '🎨',
    license: 'Complete terms in LICENSE.txt',
    fileCount: 3,
    lastUpdated: new Date().toISOString(),
  },
  {
    name: 'pdf',
    description: 'Process PDFs: read, extract, merge, split, create',
    category: 'Tools',
    icon: '📄',
    license: 'Proprietary',
    fileCount: 12,
    lastUpdated: new Date(Date.now() - 86400000 * 3).toISOString(), // 3 days ago
  },
  {
    name: 'claude-api',
    description: 'Build apps with Claude API or Anthropic SDK',
    category: 'Data & AI',
    icon: '🤖',
    license: 'Complete terms in LICENSE.txt',
    fileCount: 27,
    lastUpdated: new Date(Date.now() - 86400000 * 7).toISOString(), // 7 days ago
  },
];

export const mockCategories = ['All', 'Content', 'Data & AI', 'Development', 'Testing', 'Tools'];

export const mockSkillDetail = {
  ...mockSkills[0],
  content: '# Frontend Design\n\nThis is the skill content.\n\n## Usage\n\nUse it to build UIs.',
  installPaths: {
    claudeCode: '~/.claude/skills/frontend-design',
    opencode: '~/.opencode/skills/frontend-design',
  },
  repoPath: '/path/to/skill_repo/frontend-design',
};

export function setupFetchMock(overrides = {}) {
  const defaultResponses = {
    '/api/skills': { skills: mockSkills, categories: mockCategories },
    '/api/skills/frontend-design': mockSkillDetail,
  };
  const responses = { ...defaultResponses, ...overrides };

  global.fetch = vi.fn((url) => {
    const path = url.split('?')[0];
    const data = responses[path];
    if (data) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(data),
      });
    }
    return Promise.resolve({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ error: 'Not found' }),
    });
  });
}
