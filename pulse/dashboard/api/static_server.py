#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'ui' / 'dist'

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Serve built files
        p = ROOT / path.lstrip('/')
        if p.is_dir():
            p = p / 'index.html'
        if not p.exists():
            p = ROOT / 'index.html'
        return str(p)

if __name__ == '__main__':
    HTTPServer(('0.0.0.0', 8081), Handler).serve_forever()
