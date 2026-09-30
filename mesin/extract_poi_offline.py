"""Ekstrak POI OSM node/way/relation, dengan checkpoint dan geometri area."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time
from shapely.geometry import Point,LineString,Polygon,shape,mapping
from shapely.ops import polygonize,unary_union,transform
from pyproj import Transformer
from pbf_reader import blocks,primitives,fields,tags,unpack_field

BASE=Path(__file__).parent;WORK=BASE.parent/'work'/'poi_extract';OUT=BASE/'network_diy'/'poi'

def kind(t):
    if t.get('amenity')=='school':return 'school'
    if t.get('amenity')=='marketplace':return 'market'
    if t.get('shop')=='mall':return 'mall'
    return None


def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')

def load(p):return json.loads(p.read_text(encoding='utf-8'))


def run(source):
    WORK.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    signature={'source':str(source.resolve()),'size':source.stat().st_size,'mtime':source.stat().st_mtime_ns,'version':1}
    manifest=WORK/'manifest.json'
    if manifest.exists() and load(manifest)!=signature:raise ValueError('Checkpoint berbeda sumber; gunakan folder kerja baru.')
    save(manifest,signature)
    objects=[];refs={};locations={};size=signature['size']
    for stage in [1,2,3]:
        cp=WORK/f'stage{stage}.json'
        if cp.exists():
            print(f'Tahap {stage}: memakai checkpoint.',flush=True)
            d=load(cp)
            if stage==1:objects=d['objects'];refs=d['refs']
            elif stage==2:refs=d
            else:locations=d
            continue
        needed_ways={str(mid) for obj in objects for typ,mid,role in obj.get('members',[]) if typ==1}
        needed_nodes={int(obj['id']) for obj in objects if obj['type']=='node'}
        if stage==3:
            for rr in refs.values():needed_nodes.update(rr)
            needed_nodes.update(mid for obj in objects for typ,mid,role in obj.get('members',[]) if typ==0)
        print(f'[{stage}/3] '+{1:'Mencari sekolah, pasar dan mal',2:'Membaca anggota area POI',3:'Mengambil koordinat POI'}[stage],flush=True)
        last=time.monotonic()
        for raw,pos in blocks(source):
            strings,gran,lato,lono,groups=primitives(raw)
            if time.monotonic()-last>20:print(f'  Tahap {stage}: {pos/size:.0%}',flush=True);last=time.monotonic()
            if stage==1 and not set(strings)&{'school','marketplace','mall'}:continue
            for group in groups:
                for typ,encoded in fields(group):
                    if typ in (3,4) and stage in (1,2):
                        if stage==2:
                            if typ!=3:continue
                            oid=str(next(v for k,v in fields(encoded) if k==1))
                            if oid not in needed_ways:continue
                            item=list(fields(encoded));refs[oid]=list(unpack_field(item,8,True,True));continue
                        item=list(fields(encoded));t=tags(item,strings);cat=kind(t)
                        if cat is None:continue
                        oid=str(next(v for k,v in item if k==1));obj={'id':oid,'type':'way' if typ==3 else 'relation','kind':cat,'tags':t}
                        if typ==3:refs[oid]=list(unpack_field(item,8,True,True))
                        else:obj['members']=[(mt,mid,strings[role]) for mt,mid,role in zip(unpack_field(item,10),unpack_field(item,9,True,True),unpack_field(item,8),strict=True)]
                        objects.append(obj)
                    elif typ==1 and stage in (1,3):
                        item=list(fields(encoded));v=dict(item);oid=(v[1]>>1)^-(v[1]&1)
                        if stage==1:
                            t=tags(item,strings);cat=kind(t)
                            if cat:objects.append({'id':str(oid),'type':'node','kind':cat,'tags':t})
                        elif oid in needed_nodes:
                            lat=(v[8]>>1)^-(v[8]&1);lon=(v[9]>>1)^-(v[9]&1)
                            locations[str(oid)]=[(lono+gran*lon)*1e-9,(lato+gran*lat)*1e-9]
                    elif typ==2 and stage in (1,3):
                        item=list(fields(encoded));ids=list(unpack_field(item,1,True,True))
                        if stage==1:
                            kv=iter(unpack_field(item,10))
                            for oid in ids:
                                t={}
                                for key in kv:
                                    if key==0:break
                                    t[strings[key]]=strings[next(kv)]
                                cat=kind(t)
                                if cat:objects.append({'id':str(oid),'type':'node','kind':cat,'tags':t})
                        elif any(n in needed_nodes for n in ids):
                            for oid,lat,lon in zip(ids,unpack_field(item,8,True,True),unpack_field(item,9,True,True),strict=True):
                                if oid in needed_nodes:locations[str(oid)]=[(lono+gran*lon)*1e-9,(lato+gran*lat)*1e-9]
        save(cp,{'objects':objects,'refs':refs} if stage==1 else refs if stage==2 else locations)
    print('Membentuk geometri POI dan menyaring wilayah...',flush=True)
    projected=Transformer.from_crs(4326,32749,always_xy=True).transform
    raw=load(BASE/'network_diy/network_extract.json');region=shape(raw['region']).buffer(200)
    features=[];unresolved=[];counts=Counter()
    for obj in objects:
        geometry_notes=[]
        def way_coords(wid):
            rr=refs.get(str(wid),[])
            if not rr or any(str(n) not in locations for n in rr):raise ValueError('missing_nodes')
            return [locations[str(n)] for n in rr]
        try:
            if obj['type']=='node':geom=Point(locations[obj['id']])
            elif obj['type']=='way':
                pts=way_coords(obj['id'])
                if len(pts)>=4 and pts[0]==pts[-1]:geom=Polygon(pts)
                else:raise ValueError('open_way_not_area')
            else:
                if obj['tags'].get('type') not in {'multipolygon','boundary'}:raise ValueError('relation_not_multipolygon')
                outer=[];inner=[]
                for mt,mid,role in obj['members']:
                    if mt==2:raise ValueError('nested_relation')
                    if mt!=1:continue
                    if role=='balcony':
                        geometry_notes.append('Nonstandard balcony member ignored; closed outer footprint used')
                        continue
                    if role not in ('','outer','inner'):raise ValueError('unknown_role')
                    (inner if role=='inner' else outer).append(LineString(way_coords(mid)))
                if not outer:raise ValueError('no_outer')
                outer_rings=list(polygonize(unary_union(outer)));inner_rings=list(polygonize(unary_union(inner))) if inner else []
                if not outer_rings:raise ValueError('outer_does_not_close')
                outer_geom=unary_union(outer_rings)
                if not unary_union([p.boundary for p in outer_rings]).buffer(1e-10).covers(unary_union(outer)):raise ValueError('unclosed_outer_fragment')
                if inner and not inner_rings:raise ValueError('inner_does_not_close')
                inner_geom=unary_union(inner_rings)
                if inner and not unary_union([p.boundary for p in inner_rings]).buffer(1e-10).covers(unary_union(inner)):raise ValueError('unclosed_inner_fragment')
                if inner and not outer_geom.covers(inner_geom):raise ValueError('inner_outside_outer')
                geom=outer_geom.difference(inner_geom)
            if geom.is_empty or not geom.is_valid:raise ValueError('invalid_geometry')
            if not transform(projected,geom).intersects(region):continue
            props={'osm_type':obj['type'],'osm_id':obj['id'],'kind':obj['kind'],'name':obj['tags'].get('name',''),'source_tags':obj['tags'],'geometry_notes':geometry_notes}
            features.append({'type':'Feature','geometry':mapping(geom),'properties':props});counts[obj['kind']]+=1
        except (ValueError,KeyError) as e:unresolved.append({'osm_type':obj['type'],'osm_id':obj['id'],'kind':obj['kind'],'name':obj['tags'].get('name',''),'reason':str(e)})
    save(OUT/'poi_features.geojson',{'type':'FeatureCollection','features':features})
    save(OUT/'poi_unresolved_java.json',unresolved)
    report={'source':signature,'region':'same DIY road buffer plus 200 m for edge effects','counts':dict(counts),'java_objects_examined':len(objects),'java_unresolved_objects':len(unresolved),'status':'OSM location proxies, not measured congestion','duplicate_policy':'Union influence areas per category; repeated same-category coverage counted once'}
    save(OUT/'extraction_report.json',report);print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('pbf',type=Path);run(p.parse_args().pbf)
