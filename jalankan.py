"""Start the packaged web with the packaged Python, without PowerShell scripts."""
import json
from pathlib import Path
import socket
import subprocess
import sys

root = Path(__file__).resolve().parent
port = json.loads((root / 'web/config.json').read_text())['port']
try:
    with socket.create_connection(('127.0.0.1', port), timeout=1):
        print(f'Port {port} masih dipakai. Tutup terminal server RuteSiaga lama dengan Ctrl+C, lalu buka peluncur ini lagi.')
        raise SystemExit(1)
except OSError:
    pass
raise SystemExit(subprocess.call([sys.executable, str(root / 'web/server.py'), '--open'], cwd=root / 'web'))
