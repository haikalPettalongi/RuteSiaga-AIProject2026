"""Lokalisasi objek POI yang gagal dibentuk; tidak mengubah data sumber."""
import json
from pathlib import Path
from shapely.geometry import shape,Point
from pyproj import Transformer
BASE=Path(__file__).parent/'network_diy';WORK=BASE.parent.parent/'work/poi_extract'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def run():
    unresolved=load(BASE/'poi/poi_unresolved_java.json')
    objects=load(WORK/'stage1.json')['objects'];refs=load(WORK/'stage2.json');locs=load(WORK/'stage3.json')
    lookup={(o['type'],o['id']):o for o in objects}
    region=shape(load(BASE/'network_extract.json')['region']).buffer(200)
    project=Transformer.from_crs(4326,32749,always_xy=True).transform
    review=[];unknown=[]
    for row in unresolved:
        o=lookup[(row['osm_type'],row['osm_id'])];ids=[]
        if o['type']=='node':ids=[o['id']]
        elif o['type']=='way':ids=[str(n) for n in refs.get(o['id'],[])]
        else:
            for typ,mid,role in o['members']:
                if typ==0:ids.append(str(mid))
                if typ==1:ids.extend(str(n) for n in refs.get(str(mid),[]))
        coordinates=[locs[n] for n in ids if n in locs]
        if any(region.covers(Point(project(*xy))) for xy in coordinates):review.append(row)
        elif not coordinates:unknown.append(row)
    report={'unresolved_java':len(unresolved),'unresolved_with_known_vertices_in_model_region':review,'unresolved_without_locatable_vertices':unknown,'note':'Unresolved objects are excluded; absence of a known in-region vertex is not proof of non-intersection.'}
    (BASE/'poi/geometry_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':run()
