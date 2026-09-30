"""Tambahkan panjang paparan POI dan biaya skenario tanpa mengubah topologi."""
from collections import Counter
import json
import math
from pathlib import Path
import time
from projection_diy import Transformer
from shapely.geometry import shape,LineString,mapping
from shapely.ops import transform,unary_union
from shapely import STRtree
from ambulance_router import edge_cost,POI_SECONDS,SIGNAL_SECONDS,RAIL_SECONDS,SCENARIOS

BASE=Path(__file__).parent/'network_diy'
RADII={'school':100,'market':150,'mall':200}


def make_zone(geometries,radius):
    zone=unary_union([g.buffer(radius,quad_segs=32) for g in geometries])
    components=list(zone.geoms) if hasattr(zone,'geoms') else [zone]
    components=[g for g in components if not g.is_empty]
    return zone,components,STRtree(components)


def covered_length(line,components,tree):
    return sum(line.intersection(components[int(i)]).length for i in tree.query(line,predicate='intersects'))


def run():
    graph=json.loads((BASE/'graph_diy.json').read_text(encoding='utf-8'))
    attrs=json.loads((BASE/'way_attributes.json').read_text(encoding='utf-8'))
    features=json.loads((BASE/'poi/poi_features.geojson').read_text(encoding='utf-8'))['features']
    project=Transformer.from_crs(4326,32749,always_xy=True).transform
    grouped={k:[] for k in RADII}
    for f in features:grouped[f['properties']['kind']].append(transform(project,shape(f['geometry'])))
    zones={};zone_features=[]
    for k,r in RADII.items():
        print('Membentuk zona:',k,len(grouped[k]),'objek',flush=True)
        zone,components,tree=make_zone(grouped[k],r);zones[k]=(components,tree)
        zone_features.append({'type':'Feature','geometry':mapping(zone),'properties':{'kind':k,'radius_m':r}})
    (BASE/'poi/influence_zones_utm49s.json').write_text(json.dumps({'crs':'EPSG:32749','features':zone_features}),encoding='utf-8')
    cache={};count=Counter();stats={s:{'positive_poi_edges':0,'max_poi_s':0.0} for s in SCENARIOS};begin=time.monotonic()
    for i,e in enumerate(graph['edges']):
        t=attrs[e['way_id']]
        elevated=t.get('bridge','no') not in ('no','false','0') or t.get('tunnel','no') not in ('no','false','0')
        key=(tuple(sorted((e['u'],e['v']))),elevated)
        if key not in cache:
            line=LineString([graph['nodes'][e['u']],graph['nodes'][e['v']]])
            raw={k:0.0 if elevated else covered_length(line,*zones[k]) for k in RADII}
            assert all(-1e-7<=v<=e['length_m']+1e-6 for v in raw.values())
            cache[key]={k:min(e['length_m'],max(0.0,v)) for k,v in raw.items()}
        e['exposure_m']=cache[key]
        e['poi_grade_separation_excluded']=elevated
        count['grade_separated_edges_excluded' if elevated else 'at_grade_edges']+=1
        for k,dist in e['exposure_m'].items():
            if dist>1e-7:count[k+'_exposed_edges']+=1
        e['scenario_cost_s']={}
        for s in SCENARIOS:
            components=edge_cost(e,s);cost=sum(components.values())
            assert math.isfinite(cost) and cost>0
            assert cost+1e-9>=e['length_m']/(60/3.6)
            e['scenario_cost_s'][s]=cost
            stats[s]['positive_poi_edges']+=components['poi_s']>1e-7
            stats[s]['max_poi_s']=max(stats[s]['max_poi_s'],components['poi_s'])
        if time.monotonic()-begin>20:
            print(f"Menghitung paparan: {i+1:,}/{len(graph['edges']):,} ruas",flush=True);begin=time.monotonic()
    graph['cost_status']='base + POI exposure + signal/rail node priors; static weekday scenarios, not calibrated'
    graph['cost_parameters']={'radii_m':RADII,'poi_seconds_per_100m':POI_SECONDS,'signal_seconds':SIGNAL_SECONDS,'rail_seconds':RAIL_SECONDS,'scenario_order':SCENARIOS,'overlap_policy':'union within category; sum across categories','grade_separation_policy':'bridge/tunnel edge segments get zero POI exposure','geometry_units':'EPSG:32749 meters','buffer_quad_segs':32}
    path=BASE/'graph_diy_poi.json';path.write_text(json.dumps(graph,ensure_ascii=False),encoding='utf-8')
    report={'nodes':len(graph['nodes']),'directed_edges':len(graph['edges']),'goals':len(graph['goals']),'poi_objects':{k:len(v) for k,v in grouped.items()},'edge_counts':dict(count),'scenario_stats':stats,'parameters':graph['cost_parameters'],'validation':'all exposures within edge length, all scenario costs finite positive and >= geometric lower bound','limitations':['POIs and their footprints depend on OSM completeness','Overlapping categories may represent shared congestion; not calibrated','Bridge/tunnel exclusion is coarse and does not resolve all physical separation','Signal/rail physical-event deduplication remains pending','Frozen departure-time weekday scenario; not dynamic traffic']}
    (BASE/'poi/penalty_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':run()
