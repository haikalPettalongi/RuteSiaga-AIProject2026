"""Local, reproducible place index; never sends queries to a third party."""
import json, math, re, sqlite3, threading, unicodedata
from pathlib import Path
from projection_diy import forward, inverse

_lock = threading.Lock()
_items = None
_all_items = None
_all_lock = threading.Lock()

def normalize(text):
    text = ''.join(c for c in unicodedata.normalize('NFKD',str(text).casefold()) if not unicodedata.combining(c))
    text = re.sub(r'\bjl\.?\s*', 'jalan ', text)
    for short,full in [('rsup','rumah sakit umum pusat'),('rsud','rumah sakit umum daerah'),('rs','rumah sakit'),('kost','kos'),('indekos','kos')]:
        text=re.sub(r'\b'+short+r'\b',full,text)
    return ' '.join(re.findall(r'\w+', text))

def get_base_index(engine, cache):
    global _items
    with _lock:
        if _items is not None:
            return _items
        sources = [engine/'network_diy_akses_umum/access_catalog.sqlite',
                   engine/'network_diy/poi/poi_features.geojson',
                   engine/'network_diy/graph_diy_poi.json',
                   engine/'network_diy_akses_awal/hospital_goal_overrides.json']
        stamp = [(str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in sources]
        if cache.exists():
            saved = json.loads(cache.read_text(encoding='utf-8'))
            if saved.get('stamp') == [list(s) for s in stamp]:
                _items = saved['items']; return _items
        items = []; seen = set()
        db = sqlite3.connect(sources[0].as_uri()+'?mode=ro', uri=True)
        try:
            for (payload,) in db.execute('SELECT payload FROM segments'):
                s = json.loads(payload); name = s['tags'].get('name', '').strip()
                if not name: continue
                # A real midpoint on one segment, never an off-road name centroid.
                x,y = [(a+b)/2 for a,b in zip(s['a'],s['b'])]
                key = (normalize(name), math.floor(x/2000), math.floor(y/2000))
                if key in seen: continue
                seen.add(key); lon,lat = inverse(x,y)
                items.append(dict(name=name,kind='Jalan',lat=lat,lon=lon))
        finally: db.close()
        from shapely.geometry import shape
        for f in json.loads(sources[1].read_text(encoding='utf-8'))['features']:
            name = f['properties'].get('name','').strip()
            if not name: continue
            p = shape(f['geometry']).representative_point()
            items.append(dict(name=name,kind='Tempat',lon=p.x,lat=p.y))
        g = json.loads(sources[2].read_text(encoding='utf-8'))
        from hospital_goal_overrides import apply_goal_overrides
        apply_goal_overrides(g)
        for n in g['goals']:
            lon,lat = inverse(*g['nodes'][n])
            for name in g['goal_hospitals'][n]:
                items.append(dict(name=name,kind='Titik jalan RS',lat=lat,lon=lon))
        # Clearly labelled existing example, not a fabricated campus entrance.
        items.append(dict(name='UGM — contoh Jalan Pancasila',kind='Contoh lokasi',lat=-7.773595801763427,lon=110.376947373952))
        for i,item in enumerate(items): item.update(id=str(i),key=normalize(item['name']))
        cache.write_text(json.dumps(dict(stamp=stamp,items=items),ensure_ascii=False),encoding='utf-8')
        _items = items
        return items

def get_index(engine,cache):
    global _all_items
    with _all_lock:
        if _all_items is not None:return _all_items
        base=get_base_index(engine,cache)
        extra=cache.parent/'places_osm.json'
        additions=json.loads(extra.read_text(encoding='utf-8'))['items'] if extra.exists() else []
        combined=[];seen=set()
        for original in [*base,*additions]:
            i=dict(original);name_key=normalize(i['name'])
            if i['kind']=='Jalan':
                x,y=forward(i['lon'],i['lat']);key=(name_key,'road',math.floor(x/2000),math.floor(y/2000))
            else:key=(name_key,round(i['lat'],4),round(i['lon'],4))
            if key in seen:continue
            seen.add(key)
            i.update(id=str(len(combined)),key=normalize(' '.join([i['name'],i.get('aliases',''),i.get('address','')])),name_key=name_key)
            combined.append(i)
        _all_items=combined
        return combined

def search(engine, cache, query):
    query = normalize(query)
    if not 2 <= len(query) <= 100:
        raise ValueError('Ketik minimal 2 dan maksimal 100 karakter nama lokasi.')
    tokens = query.split()
    found = [i for i in get_index(engine,cache) if all(t in i['key'] for t in tokens)]
    found.sort(key=lambda i:(i['name_key'] != query,query not in [normalize(a) for a in i.get('aliases','').split(';')],not i['name_key'].startswith(query),not all(t in i['name_key'] for t in tokens),len(i['name']),i['name'],i['lat']))
    return dict(results=[{k:v for k,v in i.items() if k not in ('key','name_key')} for i in found[:12]],total=len(found),indexed=len(get_index(engine,cache)))
