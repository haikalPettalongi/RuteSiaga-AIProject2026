"""Compact, read-only road catalog: zstd-compressed grid cells that replace the 1.3 GB SQLite R-tree.

The payloads are byte-for-byte the raw catalog rows; only storage changes. Needs Python 3.14 (compression.zstd).
Each segment is stored in every grid cell its bounding box touches, so a bbox query reads a few small blocks.
"""
import json
import math
import sqlite3
import threading
from pathlib import Path
from compression import zstd

FORMAT = 1
MAJOR = ('motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
         'secondary', 'secondary_link', 'tertiary', 'tertiary_link')

_stores = {}
_lock = threading.Lock()


def compact_dir(catalog_dir):
    return Path(catalog_dir) / 'compact'


def available(catalog_dir):
    return (compact_dir(catalog_dir) / 'meta.json').exists()


class Store:
    def __init__(self, catalog_dir):
        root = compact_dir(catalog_dir)
        self.meta = json.loads((root / 'meta.json').read_text(encoding='utf-8'))
        if self.meta['format'] != FORMAT:
            raise RuntimeError('Format katalog terkompresi tidak dikenali.')
        self.zdict = zstd.ZstdDict((root / 'dict.zstd').read_bytes())
        self.root = root
        self.dbs = {}
        self.lock = threading.Lock()

    def _db(self, name):
        with self.lock:
            if name not in self.dbs:
                path = self.root / name
                self.dbs[name] = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, check_same_thread=False)
            return self.dbs[name]

    def _blocks(self, table, files, size, box):
        x0, x1, y0, y1 = box
        cells = [(cx, cy) for cx in range(math.floor(x0 / size), math.floor(x1 / size) + 1)
                 for cy in range(math.floor(y0 / size), math.floor(y1 / size) + 1)]
        by_file = {}
        for cx, cy in cells:
            by_file.setdefault(files(cx, cy), []).append((cx, cy))
        for name, group in by_file.items():
            db = self._db(name)
            with self.lock:
                for cx, cy in group:
                    row = db.execute(f'SELECT block FROM {table} WHERE cx=? AND cy=?', (cx, cy)).fetchone()
                    if row:
                        yield zstd.decompress(row[0], zstd_dict=self.zdict).decode('utf-8')

    def query(self, x, y, radius, major_only=False):
        """Segments whose bounding box touches the square around (x, y), ordered by id (same set as the R-tree query)."""
        box = (x - radius, x + radius, y - radius, y + radius)
        m = self.meta
        if major_only:
            blocks = self._blocks('major', lambda cx, cy: 'major.sqlite', m['major_cell_m'], box)
        else:
            shards = m['shards']
            blocks = self._blocks('cells', lambda cx, cy: f'cells_{(cx + cy) % shards}.sqlite', m['cell_m'], box)
        found = {}
        for block in blocks:
            for line in block.split('\n'):
                ident, payload = line.split('\t', 1)
                ident = int(ident)
                if ident in found:
                    continue
                s = json.loads(payload)
                (ax, ay), (bx, by) = s['a'], s['b']
                if min(ax, bx) <= x + radius and max(ax, bx) >= x - radius and min(ay, by) <= y + radius and max(ay, by) >= y - radius:
                    found[ident] = s
        return [found[i] for i in sorted(found)]


def store(catalog_dir):
    key = str(Path(catalog_dir).resolve())
    with _lock:
        if key not in _stores:
            _stores[key] = Store(catalog_dir)
        return _stores[key]


def query(catalog_dir, xy, radius, major_only=False):
    return store(catalog_dir).query(xy[0], xy[1], radius, major_only)
