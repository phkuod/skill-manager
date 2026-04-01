var archiver = require('archiver');
var fs = require('fs');

function sendZip(res, dirPath, zipName) {
  if (!fs.existsSync(dirPath)) {
    res.status(404).json({ error: 'Directory not found: ' + dirPath });
    return;
  }

  res.set({
    'Content-Type': 'application/zip',
    'Content-Disposition': 'attachment; filename="' + zipName + '.zip"',
  });

  var archive = archiver('zip', { zlib: { level: 9 } });

  archive.on('error', function (err) {
    res.status(500).json({ error: err.message });
  });

  archive.pipe(res);
  archive.directory(dirPath, zipName);
  archive.finalize();
}

module.exports = { sendZip: sendZip };
