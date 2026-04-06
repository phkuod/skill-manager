import io
import os
import zipfile

from django.http import HttpResponse


def create_zip_response(dir_path, zip_name):
    """Create an HttpResponse containing a ZIP of dir_path.
    Returns 404 response if directory doesn't exist."""
    if not os.path.isdir(dir_path):
        from django.http import JsonResponse
        return JsonResponse({'error': f'Directory not found: {zip_name}'}, status=404)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(dir_path):
            dirs.sort()
            for fname in sorted(files):
                abs_path = os.path.join(root, fname)
                arcname = os.path.relpath(abs_path, dir_path)
                zf.write(abs_path, arcname)

    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{zip_name}.zip"'
    return response
