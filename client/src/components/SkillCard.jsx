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
      className="rounded-xl p-4 cursor-pointer transition-all hover:scale-[1.02] hover:shadow-lg group"
      style={{
        backgroundColor: 'var(--bg-card)',
        border: '1px solid var(--border)',
      }}
    >
      {/* Top Row: Icon + Name */}
      <div className="flex items-center gap-3 mb-3">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center text-lg shrink-0"
          style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
        >
          {skill.icon}
        </div>
        <div className="min-w-0">
          <span
            className="font-semibold text-sm block truncate group-hover:underline"
            style={{ color: 'var(--text-primary)' }}
          >
            {skill.name}
          </span>
          <span className="text-[10px]" style={{ color: 'var(--text-secondary)' }}>
            {skill.fileCount} files
          </span>
        </div>
      </div>

      {/* Description */}
      <p
        className="text-xs leading-relaxed mb-3 line-clamp-2"
        style={{ color: 'var(--text-secondary)' }}
      >
        {skill.description}
      </p>

      {/* Bottom Row: Badge + Time */}
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
