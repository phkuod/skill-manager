import os
import re
import tempfile
import zipfile

from django.http import FileResponse, JsonResponse


# Spool ZIPs in memory up to this threshold; past it the SpooledTemporaryFile
# transparently spills to disk so peak memory stays bounded even for skills
# with many large files. Small zips (the common case) never touch the disk.
_SPOOL_LIMIT_BYTES = 10 * 1024 * 1024


def create_zip_response(dir_path, zip_name):
    """Stream a ZIP of dir_path back to the client.

    Returns a 404 JsonResponse if the directory doesn't exist.
    """
    if not os.path.isdir(dir_path):
        return JsonResponse({'error': f'Directory not found: {zip_name}'}, status=404)

    spooled = tempfile.SpooledTemporaryFile(max_size=_SPOOL_LIMIT_BYTES)
    pattern = re.compile(r'^(\d{8})(?:-.*)?$')
    with zipfile.ZipFile(spooled, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(dir_path):
            if root == dir_path:
                dirs[:] = [
                    d for d in dirs
                    if not (pattern.match(d)
                            and os.path.isfile(os.path.join(dir_path, d, 'SKILL.md')))
                ]
            dirs.sort()
            for fname in sorted(files):
                abs_path = os.path.join(root, fname)
                arcname = os.path.relpath(abs_path, dir_path)
                zf.write(abs_path, arcname)

    spooled.seek(0)
    response = FileResponse(spooled, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{zip_name}.zip"'
    return response
