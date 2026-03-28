import archiver from 'archiver';
import { existsSync } from 'fs';
import { resolve } from 'path';

export function sendZip(res, skillRepoPath, skillName) {
  const skillDir = resolve(skillRepoPath, skillName);

  if (!existsSync(skillDir)) {
    res.status(404).json({ error: `Skill not found: ${skillName}` });
    return;
  }

  res.set({
    'Content-Type': 'application/zip',
    'Content-Disposition': `attachment; filename="${skillName}.zip"`,
  });

  const archive = archiver('zip', { zlib: { level: 9 } });

  archive.on('error', (err) => {
    res.status(500).json({ error: err.message });
  });

  archive.pipe(res);
  archive.directory(skillDir, skillName);
  archive.finalize();
}
