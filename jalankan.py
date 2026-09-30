"""Start the packaged web with the packaged Python, without PowerShell scripts."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import urllib.request
import webbrowser

root = Path(__file__).resolve().parent
port = json.loads((root / 'web/config.json').read_text())['port']
url = f'http://127.0.0.1:{port}'
try:
    with socket.create_connection(('127.0.0.1', port), timeout=1):
        pass
except OSError:
    raise SystemExit(subprocess.call([sys.executable, str(root / 'web/server.py'), '--open'], cwd=root / 'web'))
try:
    with urllib.request.urlopen(url + '/api/health', timeout=3) as r:
        alive = json.load(r).get('ok')
except Exception:
    alive = False
if alive:
    print(f'RuteSiaga sudah berjalan di {url}. Membuka peramban...')
    webbrowser.open(url)
    raise SystemExit(0)
print(f'Port {port} dipakai program lain. Tutup program itu atau ubah port di web/config.json.')
raise SystemExit(1)
