import archiver from 'archiver';
import { existsSync } from 'fs';

export function sendZip(res, dirPath, zipName) {
  if (!existsSync(dirPath)) {
    res.status(404).json({ error: `Directory not found: ${dirPath}` });
    return;
  }

  res.set({
    'Content-Type': 'application/zip',
    'Content-Disposition': `attachment; filename="${zipName}.zip"`,
  });

  const archive = archiver('zip', { zlib: { level: 9 } });

  archive.on('error', (err) => {
    res.status(500).json({ error: err.message });
  });

  archive.pipe(res);
  archive.directory(dirPath, zipName);
  archive.finalize();
}
