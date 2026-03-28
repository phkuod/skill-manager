import { useState } from 'react';

const TABS = [
  { id: 'claude', label: 'Claude Code', pathKey: 'claudeCode' },
  { id: 'opencode', label: 'Opencode CLI', pathKey: 'opencode' },
];

export default function InstallCommands({ skill }) {
  const [activeTab, setActiveTab] = useState('claude');
  const [copied, setCopied] = useState(false);

  const tab = TABS.find((t) => t.id === activeTab);
  const targetPath = skill.installPaths[tab.pathKey];
  const command = `cp -r "${skill.repoPath}" "${targetPath}"`;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--border)' }}>
      {/* Tabs */}
      <div className="flex" style={{ borderBottom: '1px solid var(--border)' }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => { setActiveTab(t.id); setCopied(false); }}
            className="flex-1 px-4 py-2 text-xs font-medium transition-colors"
            style={
              activeTab === t.id
                ? { backgroundColor: 'var(--accent)', color: '#ffffff' }
                : { backgroundColor: 'var(--bg-secondary)', color: 'var(--text-secondary)' }
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Command */}
      <div className="p-3" style={{ backgroundColor: 'var(--bg-secondary)' }}>
        <div className="flex items-center gap-2">
          <code
            className="flex-1 text-xs p-2 rounded overflow-x-auto whitespace-nowrap"
            style={{
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border)',
            }}
          >
            {command}
          </code>
          <button
            onClick={handleCopy}
            className="px-3 py-1.5 rounded text-xs font-medium transition-colors shrink-0"
            style={{
              backgroundColor: copied ? '#059669' : 'var(--accent)',
              color: '#ffffff',
            }}
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>
        <p className="text-[10px] mt-2" style={{ color: 'var(--text-secondary)' }}>
          Paste this command in your terminal to install the skill to {tab.label}
        </p>
      </div>
    </div>
  );
}
