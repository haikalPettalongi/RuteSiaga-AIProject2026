"""Vercel entry point: exposes the RuteSiaga WSGI app defined in web/server.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'web'))
from server import app  # noqa: E402,F401
