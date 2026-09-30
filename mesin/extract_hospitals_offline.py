"""Ekstrak kandidat RS dari node, way dan relation; koordinat bukan pintu IGD."""
import argparse
import json
import time
from pathlib import Path
from shapely.geometry import Point, shape, mapping
from pbf_reader import blocks, primitives, fields, tags, unpack_field


def is_hospital(t):
    return t.get('amenity') == 'hospital' or t.get('healthcare') == 'hospital'


def run(source):
    base = Path(__file__).parent
    output = base / 'data_offline'
    output.mkdir(exist_ok=True)
    cache = json.loads((base / 'data_osm/cache/605d4458e57eb70be02cb46a4f1aedf0a1f9ce63.json').read_text(encoding='utf-8'))
    region = next(r for r in cache if r.get('osm_id') == 5616105)
    boundary = shape(region['geojson'])
    if not boundary.is_valid:
        raise ValueError('Batas DIY invalid')
    objects, needed_ways, way_refs, locations = {}, set(), {}, {}
    total = source.stat().st_size
    for stage in (1, 2, 3):
        print(f'[{stage}/3] Membaca peta lokal: ' + {1:'mencari objek rumah sakit',2:'menghubungkan anggota bangunan RS',3:'mengambil koordinat kandidat'}[stage], flush=True)
        last = time.monotonic()
        needed_nodes = set()
        if stage == 3:
            needed_nodes.update(obj['id'] for obj in objects.values() if obj['type'] == 'node')
            for refs in way_refs.values():
                needed_nodes.update(refs)
            for obj in objects.values():
                needed_nodes.update(mid for typ, mid in obj.get('members', []) if typ == 0)
        for raw, position in blocks(source):
            strings, gran, lato, lono, groups = primitives(raw)
            if time.monotonic() - last > 15:
                print(f'  Tahap {stage}: {position / total:.0%} berkas dibaca', flush=True)
                last = time.monotonic()
            # Pass 1 only needs blocks whose string table can contain hospital tags.
            if stage == 1 and 'hospital' not in strings:
                continue
            for group in groups:
                for typ, encoded in fields(group):
                    if typ in (3, 4) and stage in (1, 2):
                        item = list(fields(encoded))
                        oid = next(v for k, v in item if k == 1)
                        if stage == 2:
                            if typ == 3 and oid in needed_ways:
                                way_refs[oid] = list(unpack_field(item, 8, True, True))
                            continue
                        t = tags(item, strings)
                        if not is_hospital(t):
                            continue
                        kind = 'way' if typ == 3 else 'relation'
                        obj = {'type': kind, 'id': oid, 'tags': t}
                        if typ == 3:
                            way_refs[oid] = list(unpack_field(item, 8, True, True))
                        else:
                            obj['members'] = list(zip(unpack_field(item, 10), unpack_field(item, 9, True, True), strict=True))
                            needed_ways.update(mid for mt, mid in obj['members'] if mt == 1)
                        objects[(kind, oid)] = obj
                    elif typ == 1 and stage in (1, 3):
                        item = list(fields(encoded))
                        vals = dict(item)
                        oid = (vals[1] >> 1) ^ -(vals[1] & 1)
                        if stage == 1:
                            t = tags(item, strings)
                            if is_hospital(t):
                                objects[('node', oid)] = {'type':'node','id':oid,'tags':t}
                        elif oid in needed_nodes:
                            lat = (vals[8] >> 1) ^ -(vals[8] & 1)
                            lon = (vals[9] >> 1) ^ -(vals[9] & 1)
                            locations[oid] = ((lono + gran * lon) * 1e-9, (lato + gran * lat) * 1e-9)
                    elif typ == 2 and stage in (1, 3):
                        item = list(fields(encoded))
                        ids = list(unpack_field(item, 1, True, True))
                        if stage == 1:
                            kv = iter(unpack_field(item, 10))
                            for oid in ids:
                                t = {}
                                for key in kv:
                                    if key == 0:
                                        break
                                    t[strings[key]] = strings[next(kv)]
                                if is_hospital(t):
                                    objects[('node', oid)] = {'type':'node','id':oid,'tags':t}
                        elif any(oid in needed_nodes for oid in ids):
                            for oid, lat, lon in zip(ids, unpack_field(item,8,True,True), unpack_field(item,9,True,True), strict=True):
                                if oid in needed_nodes:
                                    locations[oid] = ((lono + gran * lon) * 1e-9, (lato + gran * lat) * 1e-9)
    features, unresolved = [], []
    for obj in objects.values():
        refs = [obj['id']] if obj['type'] == 'node' else way_refs.get(obj['id'], []) if obj['type'] == 'way' else []
        nested = False
        if obj['type'] == 'relation':
            for mt, mid in obj['members']:
                if mt == 0:
                    refs.append(mid)
                elif mt == 1:
                    refs.extend(way_refs.get(mid, []))
                else:
                    nested = True
        unique_refs = set(refs)
        coords = [locations[n] for n in unique_refs if n in locations]
        if not coords or nested or len(coords) != len(unique_refs):
            unresolved.append(obj)
            continue
        # Check all vertices, not just average. Border objects are retained for review.
        in_region = [boundary.covers(Point(xy)) for xy in coords]
        if not any(in_region):
            continue
        point = Point(sum(c[0] for c in coords)/len(coords), sum(c[1] for c in coords)/len(coords))
        props = {**obj['tags'], 'osm_type':obj['type'], 'osm_id':str(obj['id']),
                 'osm_url':f"https://www.openstreetmap.org/{obj['type']}/{obj['id']}",
                 'igd_status':'BELUM_DIVERIFIKASI', 'location_kind':'representative_not_entrance',
                 'boundary_review':not all(in_region), 'duplicate_review':'required'}
        features.append({'type':'Feature','geometry':mapping(point),'properties':props})
    (output/'hospital_candidates.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'unresolved_hospital_objects_java.json').write_text(json.dumps(unresolved,ensure_ascii=False,indent=2),encoding='utf-8')
    report = {'source':str(source),'bytes':total,'boundary_osm_relation':5616105,
              'osm_hospital_objects_java':len(objects),'candidate_objects_diy':len(features),
              'unresolved_objects_java':len(unresolved),'verified_igd':0,
              'limitations':['OSM candidates are not an official complete hospital list','Node/way/relation duplicates not merged','Representative coordinates are not IGD entrances','Region membership uses mapped vertices; border features need review'],
              'validation':'All three sequential PBF reads reached EOF; compressed blocks decoded and lengths checked'}
    (output/'inventory_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pbf',type=Path)
    run(parser.parse_args().pbf)
