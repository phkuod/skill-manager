import { useParams, useNavigate } from 'react-router-dom';
import { useSkillDetail } from '../hooks/useSkills';
import ThemeToggle from '../components/ThemeToggle';
import SkillDetail from '../components/SkillDetail';

export default function SkillPage() {
  const { name } = useParams();
  const navigate = useNavigate();
  const { skill, loading, error } = useSkillDetail(name);

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--bg-primary)' }}>
      {/* Header */}
      <header
        className="sticky top-0 z-10 backdrop-blur"
        style={{ borderBottom: '1px solid var(--border)', backgroundColor: 'var(--bg-primary)', opacity: 0.97 }}
      >
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-4">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-1 text-sm transition-colors"
            style={{ color: 'var(--accent)' }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            Back to skills
          </button>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-6xl mx-auto px-4 py-8">
        {loading && (
          <p className="text-center text-sm" style={{ color: 'var(--text-secondary)' }}>
            Loading...
          </p>
        )}
        {error && (
          <p className="text-center text-sm text-red-500">
            Error: {error}
          </p>
        )}
        {skill && <SkillDetail skill={skill} />}
      </main>
    </div>
  );
}
