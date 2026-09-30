"""Build the compact catalog (and compressed routing graph) from the raw SQLite/JSON files. Lossless.

Run from the project root:  python mesin/build_compact_catalog.py
"""
import json
import math
import sqlite3
import sys
import time
from pathlib import Path
from compression import zstd
from compact_catalog import FORMAT, MAJOR, compact_dir

BASE = Path(__file__).resolve().parent
CAT = BASE / 'network_diy_akses_umum'
CELL_M = 500
MAJOR_CELL_M = 2000
SHARDS = 4
LEVEL = 15


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def cells_for(minx, maxx, miny, maxy, size):
    return [(cx, cy) for cx in range(math.floor(minx / size), math.floor(maxx / size) + 1)
            for cy in range(math.floor(miny / size), math.floor(maxy / size) + 1)]


def main():
    raw = CAT / 'access_catalog.sqlite'
    out = compact_dir(CAT)
    out.mkdir(exist_ok=True)
    src = sqlite3.connect(raw.as_uri() + '?mode=ro', uri=True)
    total = src.execute('SELECT COUNT(*) FROM segments').fetchone()[0]
    log('segments', total)

    log('training dictionary')
    samples = [p.encode() for (p,) in src.execute('SELECT payload FROM segments WHERE id % 900 = 11')]
    zdict = zstd.train_dict(samples, 112640)
    (out / 'dict.zstd').write_bytes(zdict.dict_content)

    log('assigning cells from the R-tree bounds')
    grid = {}
    for ident, minx, maxx, miny, maxy in src.execute('SELECT id,minx,maxx,miny,maxy FROM bounds'):
        for c in cells_for(minx, maxx, miny, maxy, CELL_M):
            grid.setdefault(c, []).append(ident)
    log('cells', len(grid))

    for k in range(SHARDS):
        path = out / f'cells_{k}.sqlite'
        path.unlink(missing_ok=True)
        db = sqlite3.connect(path)
        db.execute('CREATE TABLE cells(cx INTEGER, cy INTEGER, block BLOB NOT NULL, PRIMARY KEY(cx,cy)) WITHOUT ROWID')
        db.commit()
        db.close()
    dbs = [sqlite3.connect(out / f'cells_{k}.sqlite') for k in range(SHARDS)]
    raw_bytes = packed = 0
    for n, ((cx, cy), ids) in enumerate(sorted(grid.items()), 1):
        rows = []
        for i in range(0, len(ids), 500):
            chunk = sorted(ids[i:i + 500])
            rows += src.execute(f'SELECT id,payload FROM segments WHERE id IN ({",".join("?" * len(chunk))})', chunk).fetchall()
        rows.sort()
        text = '\n'.join(f'{i}\t{p}' for i, p in rows).encode('utf-8')
        block = zstd.compress(text, level=LEVEL, zstd_dict=zdict)
        raw_bytes += len(text)
        packed += len(block)
        dbs[(cx + cy) % SHARDS].execute('INSERT INTO cells VALUES(?,?,?)', (cx, cy, block))
        if n % 2000 == 0:
            log(f'{n}/{len(grid)} cells, {raw_bytes / 1e6:.0f} MB -> {packed / 1e6:.0f} MB')
    for db in dbs:
        db.commit()
        db.execute('VACUUM')
        db.close()

    log('major roads')
    marks = ','.join('?' * len(MAJOR))
    major = {}
    query = ('SELECT s.id,s.payload,b.minx,b.maxx,b.miny,b.maxy FROM segments s JOIN bounds b ON b.id=s.id '
             f"WHERE json_extract(s.payload,'$.tags.highway') IN ({marks})")
    for ident, payload, minx, maxx, miny, maxy in src.execute(query, MAJOR):
        s = json.loads(payload)
        slim = {'a': s['a'], 'b': s['b'], 'tags': {k: v for k, v in s['tags'].items() if k in ('highway', 'name')},
                'edges': [{'blocked': all(e.get('blocked') for e in s['edges'])}]}
        line = f'{ident}\t{json.dumps(slim, separators=(",", ":"))}'
        for c in cells_for(minx, maxx, miny, maxy, MAJOR_CELL_M):
            major.setdefault(c, []).append(line)
    path = out / 'major.sqlite'
    path.unlink(missing_ok=True)
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE major(cx INTEGER, cy INTEGER, block BLOB NOT NULL, PRIMARY KEY(cx,cy)) WITHOUT ROWID')
    for (cx, cy), lines in major.items():
        db.execute('INSERT INTO major VALUES(?,?,?)', (cx, cy, zstd.compress('\n'.join(lines).encode('utf-8'), level=LEVEL, zstd_dict=zdict)))
    db.commit()
    db.execute('VACUUM')
    db.close()

    (out / 'meta.json').write_text(json.dumps({
        'format': FORMAT, 'cell_m': CELL_M, 'major_cell_m': MAJOR_CELL_M, 'shards': SHARDS, 'segments': total,
        'source': 'access_catalog.sqlite (lossless re-pack)', 'zstd_level': LEVEL}, indent=1), encoding='utf-8')

    log('compressing routing graph')
    graph = BASE / 'network_diy/graph_diy_poi.json'
    (graph.with_name(graph.name + '.zst')).write_bytes(zstd.compress(graph.read_bytes(), level=12))
    log('done')


if __name__ == '__main__':
    sys.exit(main())
