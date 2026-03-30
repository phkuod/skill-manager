import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useSkillFiles } from '../hooks/useSkills';

function parseFrontmatter(content) {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
  if (!match) return { fields: null, body: content };

  const fields = [];
  const raw = match[1];
  // Simple YAML key-value parser (handles quoted and multi-line values)
  const lines = raw.split(/\r?\n/);
  let currentKey = null;
  let currentValue = '';

  for (const line of lines) {
    const keyMatch = line.match(/^(\w[\w-]*)\s*:\s*(.*)$/);
    if (keyMatch) {
      if (currentKey) {
        fields.push({ key: currentKey, value: currentValue.replace(/^["']|["']$/g, '').trim() });
      }
      currentKey = keyMatch[1];
      currentValue = keyMatch[2];
    } else if (currentKey) {
      currentValue += ' ' + line.trim();
    }
  }
  if (currentKey) {
    fields.push({ key: currentKey, value: currentValue.replace(/^["']|["']$/g, '').trim() });
  }

  return { fields, body: match[2] };
}

function FrontmatterTable({ fields }) {
  return (
    <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
      <tbody>
        {fields.map(({ key, value }) => (
          <tr key={key} style={{ borderBottom: '1px solid var(--border)' }}>
            <td
              className="px-4 py-3 font-medium align-top whitespace-nowrap"
              style={{
                color: 'var(--accent)',
                width: '120px',
                backgroundColor: 'var(--bg-secondary)',
              }}
            >
              {key}
            </td>
            <td
              className="px-4 py-3"
              style={{ color: 'var(--text-primary)' }}
            >
              {value}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SkillMdBlock({ file }) {
  const { fields, body } = parseFrontmatter(file.content);

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ border: '1px solid var(--border)' }}
    >
      {/* Terminal-style header */}
      <div
        className="flex items-center justify-between px-4 py-2"
        style={{ backgroundColor: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <span className="w-3 h-3 rounded-full bg-red-500 opacity-80" />
            <span className="w-3 h-3 rounded-full bg-yellow-500 opacity-80" />
            <span className="w-3 h-3 rounded-full bg-green-500 opacity-80" />
          </div>
          <span className="text-xs font-mono font-medium ml-1" style={{ color: 'var(--text-primary)' }}>
            SKILL.md
          </span>
        </div>
        <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
          readonly
        </span>
      </div>

      {/* Frontmatter table */}
      {fields && fields.length > 0 && (
        <FrontmatterTable fields={fields} />
      )}

      {/* Markdown body */}
      {body.trim() && (
        <div
          className="p-4"
          style={{ backgroundColor: 'var(--bg-primary)' }}
        >
          <div className="prose prose-sm max-w-none skill-markdown" style={{ color: 'var(--text-primary)' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}

function FileBlock({ file }) {
  return (
    <div
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
  );
}

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
      {files.map((file) =>
        file.path === 'SKILL.md' ? (
          <SkillMdBlock key={file.path} file={file} />
        ) : (
          <FileBlock key={file.path} file={file} />
        )
      )}
    </div>
  );
}
