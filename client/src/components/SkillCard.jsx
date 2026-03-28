import { useNavigate } from 'react-router-dom';

const BADGE_STYLES = {
  Development: { bg: 'var(--badge-dev-bg)', color: 'var(--badge-dev-text)' },
  Content: { bg: 'var(--badge-content-bg)', color: 'var(--badge-content-text)' },
  Tools: { bg: 'var(--badge-tools-bg)', color: 'var(--badge-tools-text)' },
  'Data & AI': { bg: 'var(--badge-ai-bg)', color: 'var(--badge-ai-text)' },
  Testing: { bg: 'var(--badge-testing-bg)', color: 'var(--badge-testing-text)' },
  Other: { bg: 'var(--badge-other-bg)', color: 'var(--badge-other-text)' },
};

function timeAgo(dateStr) {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

export default function SkillCard({ skill }) {
  const navigate = useNavigate();
  const badge = BADGE_STYLES[skill.category] || BADGE_STYLES.Other;

  return (
    <div
      onClick={() => navigate(`/skill/${skill.name}`)}
      className="rounded-lg p-4 cursor-pointer transition-all hover:scale-[1.02] hover:shadow-lg"
      style={{
        backgroundColor: 'var(--bg-card)',
        border: '1px solid var(--border)',
      }}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">{skill.icon}</span>
        <span className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
          {skill.name}
        </span>
      </div>
      <p
        className="text-xs leading-relaxed mb-3 line-clamp-2"
        style={{ color: 'var(--text-secondary)' }}
      >
        {skill.description}
      </p>
      <div className="flex items-center justify-between">
        <span
          className="text-[10px] font-medium px-2 py-0.5 rounded"
          style={{ backgroundColor: badge.bg, color: badge.color }}
        >
          {skill.category}
        </span>
        <span className="text-[10px]" style={{ color: 'var(--text-secondary)' }}>
          Updated {timeAgo(skill.lastUpdated)}
        </span>
      </div>
    </div>
  );
}
