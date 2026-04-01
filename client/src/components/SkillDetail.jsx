import { useState } from 'react';
import InstallCommands from './InstallCommands';
import SkillFiles from './SkillFiles';
import { useSkillVersion } from '../hooks/useSkills';

const BADGE_STYLES = {
  Development: { bg: 'var(--badge-dev-bg)', color: 'var(--badge-dev-text)' },
  Content: { bg: 'var(--badge-content-bg)', color: 'var(--badge-content-text)' },
  Tools: { bg: 'var(--badge-tools-bg)', color: 'var(--badge-tools-text)' },
  'Data & AI': { bg: 'var(--badge-ai-bg)', color: 'var(--badge-ai-text)' },
  Testing: { bg: 'var(--badge-testing-bg)', color: 'var(--badge-testing-text)' },
  Other: { bg: 'var(--badge-other-bg)', color: 'var(--badge-other-text)' },
};

export default function SkillDetail({ skill }) {
  const [selectedVersion, setSelectedVersion] = useState(null);
  const { skill: versionSkill, loading: versionLoading } = useSkillVersion(
    skill.name,
    selectedVersion
  );

  // Use version data if a non-current version is selected, otherwise use default skill data
  const displaySkill = versionSkill || skill;
  const badge = BADGE_STYLES[skill.category] || BADGE_STYLES.Other;

  const handleDownload = () => {
    if (selectedVersion) {
      window.open(`/api/skills/${encodeURIComponent(skill.name)}/versions/${encodeURIComponent(selectedVersion)}/zip`, '_blank');
    } else {
      window.open(`/api/skills/${encodeURIComponent(skill.name)}/zip`, '_blank');
    }
  };

  return (
    <div>
      {/* Hero Header */}
      <div
        className="rounded-xl p-6 mb-6"
        style={{
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border)',
        }}
      >
        <div className="flex items-start gap-4">
          <div
            className="w-14 h-14 rounded-xl flex items-center justify-center text-2xl shrink-0"
            style={{ backgroundColor: 'var(--bg-primary)', border: '1px solid var(--border)' }}
          >
            {skill.icon}
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--text-primary)' }}>
              {displaySkill.name}
            </h1>
            <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
              {displaySkill.description}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <span
                className="px-2.5 py-1 rounded-md text-xs font-medium"
                style={{ backgroundColor: badge.bg, color: badge.color }}
              >
                {skill.category}
              </span>
              <span
                className="px-2.5 py-1 rounded-md text-xs"
                style={{ backgroundColor: 'var(--bg-primary)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
              >
                {displaySkill.license}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Version Selector */}
      {skill.versions && skill.versions.length > 0 && (
        <div
          className="rounded-xl p-4 mb-6 flex items-center gap-3"
          style={{
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
          }}
        >
          <label
            className="text-sm font-medium shrink-0"
            style={{ color: 'var(--text-primary)' }}
            htmlFor="version-select"
          >
            Version
          </label>
          <select
            id="version-select"
            value={selectedVersion || ''}
            onChange={(e) => setSelectedVersion(e.target.value || null)}
            className="flex-1 text-sm rounded-lg px-3 py-2 outline-none"
            style={{
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border)',
            }}
          >
            <option value="">
              {skill.currentVersion} (latest)
            </option>
            {skill.versions
              .filter((v) => v.version !== skill.currentVersion)
              .map((v) => (
                <option key={v.version} value={v.version}>
                  {v.version}
                </option>
              ))}
          </select>
          {versionLoading && (
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              Loading...
            </span>
          )}
        </div>
      )}

      {/* Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Main Content — Left */}
        <div className="lg:col-span-8 space-y-6">
          {/* Install Section */}
          <div>
            <h2
              className="text-sm font-semibold mb-3 flex items-center gap-2"
              style={{ color: 'var(--text-primary)' }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="4 17 10 11 4 5" />
                <line x1="12" y1="19" x2="20" y2="19" />
              </svg>
              Install
            </h2>
            <InstallCommands skill={displaySkill} />
          </div>

          {/* Documentation */}
          <div>
            <h2
              className="text-sm font-semibold mb-3 flex items-center gap-2"
              style={{ color: 'var(--text-primary)' }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10 9 9 9 8 9" />
              </svg>
              Documentation
            </h2>
            <SkillFiles name={skill.name} version={selectedVersion} />
          </div>
        </div>

        {/* Sidebar — Right */}
        <div className="lg:col-span-4 space-y-4">
          {/* Stats Card */}
          <div
            className="rounded-xl p-5"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
            }}
          >
            <h3 className="text-xs font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--text-secondary)' }}>
              Details
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
                    <polyline points="13 2 13 9 20 9" />
                  </svg>
                  Files
                </span>
                <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
                  {displaySkill.fileCount} files
                </span>
              </div>
              <div
                className="h-px"
                style={{ backgroundColor: 'var(--border)' }}
              />
              <div className="flex items-center justify-between">
                <span className="text-xs flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                  License
                </span>
                <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
                  {displaySkill.license}
                </span>
              </div>
              <div
                className="h-px"
                style={{ backgroundColor: 'var(--border)' }}
              />
              <div className="flex items-center justify-between">
                <span className="text-xs flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                  </svg>
                  Updated
                </span>
                <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
                  {new Date(displaySkill.lastUpdated).toLocaleDateString()}
                </span>
              </div>
              <div
                className="h-px"
                style={{ backgroundColor: 'var(--border)' }}
              />
              <div className="flex items-center justify-between">
                <span className="text-xs flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
                    <line x1="7" y1="7" x2="7.01" y2="7" />
                  </svg>
                  Category
                </span>
                <span
                  className="text-xs font-medium px-2 py-0.5 rounded"
                  style={{ backgroundColor: badge.bg, color: badge.color }}
                >
                  {skill.category}
                </span>
              </div>
            </div>
          </div>

          {/* Install Paths Card */}
          <div
            className="rounded-xl p-5"
            style={{
              backgroundColor: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
            }}
          >
            <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-secondary)' }}>
              Install Paths
            </h3>
            <div className="space-y-2">
              <div>
                <span className="text-[10px] font-medium" style={{ color: 'var(--text-secondary)' }}>Claude Code</span>
                <div
                  className="text-xs mt-1 p-2 rounded-lg font-mono truncate"
                  style={{
                    backgroundColor: 'var(--bg-primary)',
                    border: '1px solid var(--border)',
                    color: 'var(--text-primary)',
                  }}
                >
                  {displaySkill.installPaths.claudeCode}
                </div>
              </div>
              <div>
                <span className="text-[10px] font-medium" style={{ color: 'var(--text-secondary)' }}>Opencode CLI</span>
                <div
                  className="text-xs mt-1 p-2 rounded-lg font-mono truncate"
                  style={{
                    backgroundColor: 'var(--bg-primary)',
                    border: '1px solid var(--border)',
                    color: 'var(--text-primary)',
                  }}
                >
                  {displaySkill.installPaths.opencode}
                </div>
              </div>
            </div>
          </div>

          {/* Download Button */}
          <button
            onClick={handleDownload}
            className="w-full px-4 py-3 rounded-xl text-sm font-medium transition-all flex items-center justify-center gap-2 hover:opacity-90"
            style={{
              backgroundColor: 'var(--accent)',
              color: '#ffffff',
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            Download ZIP
          </button>
        </div>
      </div>
    </div>
  );
}
