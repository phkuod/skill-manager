"""Minimal static server for the frontend container.

Handles two quirks that plain `python -m http.server` cannot:
  1. SPA-style fallback: /skill/<name> -> skill.html (JS reads location.pathname)
  2. /static/* alias: HTML references /static/assets/... but the actual files
     live at /assets/... in the frontend directory.
"""
import http.server
import socketserver
import os

PORT = 8080
ROOT = '/srv/frontend'
os.chdir(ROOT)


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/skill/'):
            self.path = '/skill.html'
        elif self.path.startswith('/static/'):
            self.path = self.path[len('/static'):]
        return super().do_GET()


with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
    print(f"[frontend] serving {ROOT} on :{PORT}", flush=True)
    httpd.serve_forever()
