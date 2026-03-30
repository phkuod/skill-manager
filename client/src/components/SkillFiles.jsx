import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useSkillFiles } from '../hooks/useSkills';

export default function SkillFiles({ name }) {
  const { files, loading, error } = useSkillFiles(name);

  if (loading) {
    return (
      <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
        Loading files…
      </p>
    );
  }

  if (error) {
    return (
      <p className="text-sm text-red-500">
        Failed to load files: {error}
      </p>
    );
  }

  if (files.length === 0) {
    return (
      <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
        No files found
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {files.map((file) => (
        <div
          key={file.path}
          className="rounded-xl overflow-hidden"
          style={{ border: '1px solid var(--border)' }}
        >
          {/* File header */}
          <div
            className="flex items-center justify-between px-4 py-2"
            style={{ backgroundColor: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}
          >
            <span className="text-xs font-mono font-medium" style={{ color: 'var(--text-primary)' }}>
              {file.path}
            </span>
            {file.language !== 'markdown' && (
              <span
                className="text-[10px] px-2 py-0.5 rounded font-medium"
                style={{ backgroundColor: 'var(--bg-primary)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
              >
                {file.language}
              </span>
            )}
          </div>

          {/* File body */}
          <div
            className="p-4"
            style={{ backgroundColor: 'var(--bg-primary)' }}
          >
            {file.truncated ? (
              <p className="text-xs italic" style={{ color: 'var(--text-secondary)' }}>
                File too large to preview
              </p>
            ) : file.language === 'markdown' ? (
              <div className="prose prose-sm max-w-none skill-markdown" style={{ color: 'var(--text-primary)' }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{file.content}</ReactMarkdown>
              </div>
            ) : (
              <pre
                className="text-xs overflow-x-auto"
                style={{ color: 'var(--text-primary)', margin: 0 }}
              >
                <code>{file.content}</code>
              </pre>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
