import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import InstallCommands from './InstallCommands';

const BADGE_STYLES = {
  Development: { bg: 'var(--badge-dev-bg)', color: 'var(--badge-dev-text)' },
  Content: { bg: 'var(--badge-content-bg)', color: 'var(--badge-content-text)' },
  Tools: { bg: 'var(--badge-tools-bg)', color: 'var(--badge-tools-text)' },
  'Data & AI': { bg: 'var(--badge-ai-bg)', color: 'var(--badge-ai-text)' },
  Testing: { bg: 'var(--badge-testing-bg)', color: 'var(--badge-testing-text)' },
  Other: { bg: 'var(--badge-other-bg)', color: 'var(--badge-other-text)' },
};

export default function SkillDetail({ skill }) {
  const badge = BADGE_STYLES[skill.category] || BADGE_STYLES.Other;

  const handleDownload = () => {
    window.open(`/api/skills/${skill.name}/zip`, '_blank');
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <span className="text-3xl">{skill.icon}</span>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            {skill.name}
          </h1>
        </div>
        <p className="text-sm mb-3" style={{ color: 'var(--text-secondary)' }}>
          {skill.description}
        </p>
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <span
            className="px-2 py-0.5 rounded font-medium"
            style={{ backgroundColor: badge.bg, color: badge.color }}
          >
            {skill.category}
          </span>
          <span style={{ color: 'var(--text-secondary)' }}>
            {skill.fileCount} files
          </span>
          <span style={{ color: 'var(--text-secondary)' }}>
            {skill.license}
          </span>
          <span style={{ color: 'var(--text-secondary)' }}>
            Updated {new Date(skill.lastUpdated).toLocaleDateString()}
          </span>
        </div>
      </div>

      {/* Install Section */}
      <div className="mb-6">
        <h2 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
          Install
        </h2>
        <InstallCommands skill={skill} />
      </div>

      {/* Download ZIP */}
      <div className="mb-8">
        <button
          onClick={handleDownload}
          className="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          style={{
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
            color: 'var(--text-primary)',
          }}
        >
          Download ZIP
        </button>
      </div>

      {/* Skill Content (Markdown) */}
      <div className="mb-8">
        <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
          Documentation
        </h2>
        <div
          className="prose prose-sm max-w-none rounded-lg p-6 skill-markdown"
          style={{
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
            color: 'var(--text-primary)',
          }}
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{skill.content}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
