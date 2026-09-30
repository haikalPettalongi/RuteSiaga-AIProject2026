"""Jaringan jalan DIY offline, konservatif; tidak mengklaim validasi lapangan."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import time
import networkx as nx
from projection_diy import Transformer
from shapely.geometry import shape, LineString, Point, mapping
from shapely.ops import transform
from shapely.prepared import prep
from pbf_reader import blocks, primitives, fields, unpack_field, tags
from ambulance_router import SPEED_KMH

BASE=Path(__file__).parent
MAJOR=set(SPEED_KMH)-{'residential','unclassified','service'}
ALLOWED_ACCESS={'yes','permissive','designated','official'}

def numeric(s):
    m=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(m)?\s*',s or '')
    return float(m[1]) if m else None


def access_ok(t):
    for key in ('motorcar','motor_vehicle','vehicle','access'):
        if key in t:
            return t[key] in ALLOWED_ACCESS
    return True


def road_policy(t):
    h=t.get('highway','')
    if h not in SPEED_KMH or t.get('area')=='yes': return 'excluded_class'
    if any('conditional' in k or k in ('access:forward','access:backward','vehicle:forward','vehicle:backward','motor_vehicle:forward','motor_vehicle:backward','motorcar:forward','motorcar:backward') for k in t): return 'conditional_or_directional_access_review'
    if not access_ok(t): return 'restricted_access'
    if any(t.get(k) not in (None,'no') for k in ('construction','proposed')): return 'construction'
    for k in ('width','maxwidth','maxwidth:physical'):
        if k in t:
            width=numeric(t[k])
            if width is None: return 'width_unparsed_review'
            if width<3: return 'width_below_3m'
    if any(k in t for k in ('maxheight','maxweight','maxaxleload','maxlength')): return 'vehicle_dimensions_review'
    if t.get('surface') in {'sand','mud','ground','dirt','grass','earth'} or t.get('smoothness') in {'bad','very_bad','horrible','very_horrible','impassable'}: return 'surface_review'
    if h not in MAJOR:
        if h=='service': return 'service_requires_access_audit'
        if numeric(t.get('width')) is None: return 'local_width_missing'
    value=t.get('oneway:motorcar',t.get('oneway:motor_vehicle',t.get('oneway','')))
    if value not in {'','yes','true','1','no','false','0','-1'}: return 'oneway_ambiguous'
    return 'allowed'


def directions(t):
    v=t.get('oneway:motorcar',t.get('oneway:motor_vehicle',t.get('oneway','')))
    if v=='-1': return (-1,)
    if v in ('yes','true','1'): return (1,)
    if v in ('no','false','0'): return (1,-1)
    if t.get('junction')=='roundabout' or t.get('highway')=='motorway': return (1,)
    return (1,-1)


def extract(source, output):
    cached=json.loads((BASE/'data_osm/cache/605d4458e57eb70be02cb46a4f1aedf0a1f9ce63.json').read_text(encoding='utf-8'))
    boundary=shape(next(r for r in cached if r['osm_id']==5616105)['geojson'])
    project=Transformer.from_crs(4326,32749,always_xy=True).transform
    inverse=Transformer.from_crs(32749,4326,always_xy=True).transform
    region=transform(project,boundary).buffer(10000)
    bbox=transform(inverse,region).bounds
    minx,miny,maxx,maxy=bbox
    node_data={}; roads=[]; restrictions=[]; counts=Counter(); last=time.monotonic(); size=source.stat().st_size
    print('[1/4] Membaca node dan ruas dari PBF lokal...',flush=True)
    seen_ways=False
    for raw,pos in blocks(source):
        strings,gran,lato,lono,groups=primitives(raw)
        if time.monotonic()-last>20:
            print(f'  {pos/size:.0%}; node wilayah {len(node_data):,}; ruas kandidat {len(roads):,}',flush=True);last=time.monotonic()
        for group in groups:
            for typ,encoded in fields(group):
                if typ==2:
                    if seen_ways: raise ValueError('Input tidak node-first; perlu sort PBF')
                    item=list(fields(encoded)); kv=iter(unpack_field(item,10))
                    for oid,lat,lon in zip(unpack_field(item,1,True,True),unpack_field(item,8,True,True),unpack_field(item,9,True,True),strict=True):
                        x=(lono+gran*lon)*1e-9; y=(lato+gran*lat)*1e-9
                        inside=minx<=x<=maxx and miny<=y<=maxy
                        t={}
                        for key in kv:
                            if key==0: break
                            value=next(kv)
                            if inside: t[strings[key]]=strings[value]
                        if inside: node_data[oid]=(x,y,t)
                elif typ==1:
                    if seen_ways: raise ValueError('Input tidak node-first')
                    item=list(fields(encoded));d=dict(item); oid=(d[1]>>1)^-(d[1]&1)
                    x=(lono+gran*((d[9]>>1)^-(d[9]&1)))*1e-9;y=(lato+gran*((d[8]>>1)^-(d[8]&1)))*1e-9
                    if minx<=x<=maxx and miny<=y<=maxy: node_data[oid]=(x,y,tags(item,strings))
                elif typ==3:
                    seen_ways=True
                    if 'highway' not in strings: continue
                    item=list(fields(encoded)); t=tags(item,strings)
                    if 'highway' not in t: continue
                    refs=list(unpack_field(item,8,True,True))
                    if not any(n in node_data for n in refs): continue
                    reason=road_policy(t);counts[reason]+=1
                    if reason=='allowed': roads.append({'id':str(next(v for k,v in item if k==1)),'refs':refs,'tags':t})
                elif typ==4:
                    if 'restriction' not in strings: continue
                    item=list(fields(encoded));t=tags(item,strings)
                    if t.get('type')!='restriction': continue
                    members=[(mt,mid,strings[role]) for mt,mid,role in zip(unpack_field(item,10),unpack_field(item,9,True,True),unpack_field(item,8),strict=True)]
                    restrictions.append({'id':str(next(v for k,v in item if k==1)),'tags':t,'members':members})
    used={n for w in roads for n in w['refs'] if n in node_data}
    nodes={str(n):node_data[n] for n in used}
    cache={'nodes':nodes,'ways':roads,'restrictions':restrictions,'policy_counts':dict(counts),'region':mapping(region),'source':str(source),'source_bytes':size}
    (output/'network_extract.json').write_text(json.dumps(cache,ensure_ascii=False),encoding='utf-8')
    return cache


def build(raw,output):
    print('[2/4] Membentuk graf berarah dan pembatasan belok...',flush=True)
    project=Transformer.from_crs(4326,32749,always_xy=True).transform
    region=prep(shape(raw['region'])); coords={n:project(v[0],v[1]) for n,v in raw['nodes'].items()}
    ways={w['id']:w for w in raw['ways']}; banned=set(); turns=[]; restriction_audit=[]
    for r in raw['restrictions']:
        t=r['tags']; members=r['members']; fr=[str(mid) for mt,mid,role in members if mt==1 and role=='from'];to=[str(mid) for mt,mid,role in members if mt==1 and role=='to'];via=[str(mid) for mt,mid,role in members if mt==0 and role=='via']
        if not set(fr)&ways.keys(): continue
        kind=t.get('restriction:motorcar',t.get('restriction:motor_vehicle',t.get('restriction')))
        if kind is None: continue
        if set(t.get('except','').split(';'))&{'motorcar','motor_vehicle','vehicle'}: continue
        supported={'no_left_turn','no_right_turn','no_straight_on','no_u_turn','only_left_turn','only_right_turn','only_straight_on','only_u_turn'}
        if len(fr)==len(to)==len(via)==1 and kind in supported and not any('conditional' in k for k in t) and not any(mt==1 and role=='via' for mt,mid,role in members):
            turns.append({'from_way':fr[0],'to_way':to[0],'via':via[0],'restriction':kind,'osm_relation':r['id']})
            restriction_audit.append({'id':r['id'],'action':'turn_state_rule'})
        else:
            banned.update(fr);restriction_audit.append({'id':r['id'],'action':'exclude_from_ways_conservatively','from':fr})
    blocked_nodes={n for n,(_,_,t) in raw['nodes'].items() if not access_ok(t) or t.get('barrier','no') not in {'no','entrance','cattle_grid','toll_booth','border_control'} or any('conditional' in k for k in t)}
    edges=[]; audit=Counter();waydirs={}
    for wid,w in ways.items():
        if wid in banned: continue
        t=w['tags'];dirs=directions(t);waydirs[wid]=list(dirs)
        for j,(a,b) in enumerate(zip(w['refs'],w['refs'][1:])):
            a,b=str(a),str(b)
            if a not in coords or b not in coords: audit['segment_missing_outside_bbox']+=1;continue
            if a in blocked_nodes or b in blocked_nodes: audit['barrier_or_node_access']+=1;continue
            if not region.covers(LineString([coords[a],coords[b]])): audit['outside_buffer']+=1;continue
            length=math.dist(coords[a],coords[b])
            if length<=0: audit['zero_length']+=1;continue
            for direction in dirs:
                u,v=(a,b) if direction==1 else (b,a)
                nt=raw['nodes'][v][2];speed=SPEED_KMH[t['highway']]
                speedtag=t.get('maxspeed:forward' if direction==1 else 'maxspeed:backward',t.get('maxspeed'))
                if speedtag:
                    match=re.fullmatch(r'(\d+(?:\.\d+)?)\s*(km/h|mph)?',speedtag)
                    if match: speed=min(speed,float(match[1])*(1.609344 if match[2]=='mph' else 1))
                    else: audit['edge_unparsed_maxspeed']+=1;continue
                if speed<=0: continue
                edges.append({'id':f'{wid}:{j}:{direction}','u':u,'v':v,'way_id':wid,'segment_index':j,'direction':direction,'length_m':length,'highway':t['highway'],'speed_kmh':speed,'signal_at_end':nt.get('highway')=='traffic_signals','rail_at_end':nt.get('railway')=='level_crossing' and t.get('bridge','no')=='no' and t.get('tunnel','no')=='no'})
    used={e[k] for e in edges for k in ('u','v')}
    graph={'status':'RESEARCH_ROAD_GRAPH_NOT_FIELD_VERIFIED','crs':'EPSG:32749','buffer_m':10000,'nodes':{n:coords[n] for n in sorted(used)},'edges':edges,'turn_restrictions':turns,'goals':[], 'cost_status':'base_signal_rail_only_POI_NOT_YET_COMPUTED'}
    (output/'way_attributes.json').write_text(json.dumps({wid:ways[wid]['tags'] for wid in waydirs},ensure_ascii=False),encoding='utf-8')
    (output/'restriction_audit.json').write_text(json.dumps(restriction_audit,indent=2),encoding='utf-8')
    print('[3/4] Memetakan lokasi RS ke titik jalan; tanpa membuat jalan fiktif...',flush=True)
    network=nx.DiGraph();network.add_nodes_from(used);network.add_edges_from((e['u'],e['v']) for e in edges)
    components=sorted(nx.weakly_connected_components(network),key=len,reverse=True)
    main=components[0]
    hospitals=json.loads((BASE/'data_offline/hospitals_general_filtered.geojson').read_text(encoding='utf-8'))['features']
    mappings=[]; goal_names={}
    # Hospital coordinates are a proxy. Nearest road node is an approach point, not a new connector edge.
    for f in hospitals:
        p=f['properties'];point=project(*f['geometry']['coordinates'])
        nearest=min(used,key=lambda n:math.dist(point,coords[n]));gap=math.dist(point,coords[nearest])
        status='road_point_proxy' if gap<=150 and nearest in main and network.in_degree(nearest)>0 else 'requires_review'
        row={'name':p['name'],'osm_url':p['osm_url'],'hospital_lonlat':f['geometry']['coordinates'],'road_node':nearest,'gap_m':round(gap,2),'status':status,'in_largest_component':nearest in main}
        mappings.append(row)
        if status=='road_point_proxy': goal_names.setdefault(nearest,[]).append(p['name'])
    graph['goals']=list(goal_names);graph['goal_hospitals']=goal_names
    (output/'hospital_road_mapping.json').write_text(json.dumps(mappings,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'graph_diy.json').write_text(json.dumps(graph,ensure_ascii=False),encoding='utf-8')
    assert len({e['id'] for e in edges})==len(edges)
    assert all(e['u'] in used and e['v'] in used and e['length_m']>0 and e['direction'] in waydirs[e['way_id']] for e in edges)
    assert all(e['u'] not in blocked_nodes and e['v'] not in blocked_nodes for e in edges)
    report={'nodes':len(used),'directed_edges':len(edges),'ways':len({e['way_id'] for e in edges}),'weak_components':len(components),'largest_component_nodes':len(main),'road_selection':raw['policy_counts'],'segment_audit':dict(audit),'turn_rules':len(turns),'unsupported_restriction_from_ways_excluded':len(banned),'hospital_candidates':len(hospitals),'hospital_road_proxies':sum(r['status']=='road_point_proxy' for r in mappings),'hospitals_need_review':sum(r['status']=='requires_review' for r in mappings),'unique_goal_nodes':len(goal_names),'buffer_m':10000,'max_hospital_gap_m':150,'source':raw['source'],'source_bytes':raw['source_bytes']}
    (output/'network_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('[4/4] Graf tersimpan. Pemeriksaan rute dijalankan terpisah.',flush=True);print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--pbf',default=r'C:\Users\LENOVO\Downloads\java-260920.osm.pbf');parser.add_argument('--reuse',action='store_true');args=parser.parse_args()
    output=BASE/'network_diy';output.mkdir(exist_ok=True)
    raw=json.loads((output/'network_extract.json').read_text(encoding='utf-8')) if args.reuse else extract(Path(args.pbf),output)
    build(raw,output)
