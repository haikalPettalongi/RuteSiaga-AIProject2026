"""General origin access overlay and direction-aware edge snapping, in meters."""
import json,math,sqlite3
from pathlib import Path
import numpy as np
from shapely.geometry import LineString,shape
from shapely import STRtree
from add_poi_penalties import covered_length
from hospital_goal_overrides import apply_goal_overrides
from build_access_catalog import ORIGINAL_POLICY
from compact_catalog import available as compact_available,query as compact_query
BASE=Path(__file__).resolve().parent
CAT=BASE/'network_diy_akses_umum'

class OriginError(ValueError):pass

def load_zones():
 zones={}
 for f in json.loads((BASE/'network_diy/poi/influence_zones_utm49s.json').read_text())['features']:
  geom=shape(f['geometry']);parts=list(geom.geoms) if hasattr(geom,'geoms') else [geom]
  zones[f['properties']['kind']]=(parts,STRtree(parts))
 return zones

def cost_geometry(e,nodes,tags,zones):
 line=LineString([nodes[e['u']],nodes[e['v']]])
 e['length_m']=line.length
 separated=tags.get('bridge','no') not in ('no','false','0') or tags.get('tunnel','no') not in ('no','false','0')
 e['exposure_m']={k:0.0 if separated else min(e['length_m'],covered_length(line,*z)) for k,z in zones.items()}
 e['poi_grade_separation_excluded']=separated
 e.pop('scenario_cost_s',None)
 return e

def project_segment(xy,a,b):
 dx,dy=b[0]-a[0],b[1]-a[1];d=dx*dx+dy*dy
 f=max(0.0,min(1.0,((xy[0]-a[0])*dx+(xy[1]-a[1])*dy)/d)) if d else 0
 p=(a[0]+f*dx,a[1]+f*dy)
 return math.dist(xy,p),f,p

def catalog_segments(xy,radius):
 if compact_available(CAT):return compact_query(CAT,xy,radius)
 path=CAT/'access_catalog.sqlite'
 if not path.exists() or not (CAT/'catalog_report.json').exists():raise OriginError('Katalog akses umum belum tersedia. Jalankan build_access_catalog.py dahulu.')
 db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
 x,y=xy
 rows=db.execute('SELECT s.payload FROM segments s JOIN bounds b ON b.id=s.id WHERE b.minx<=? AND b.maxx>=? AND b.miny<=? AND b.maxy>=?',(x+radius,x-radius,y+radius,y-radius)).fetchall();db.close()
 return [json.loads(r[0]) for r in rows]

def nearest_strict(graph,xy,attrs):
 # Vector projection avoids treating a sparse road as far from the origin.
 edges=graph['edges'];a=np.array([graph['nodes'][e['u']] for e in edges]);b=np.array([graph['nodes'][e['v']] for e in edges]);delta=b-a
 f=np.clip(np.sum((np.array(xy)-a)*delta,axis=1)/np.sum(delta*delta,axis=1),0,1)
 p=a+delta*f[:,None];d=np.linalg.norm(p-np.array(xy),axis=1);best=float(d.min())
 selected={}
 for i in np.flatnonzero(d<=best+.05):
  e=edges[int(i)];key=(e['way_id'],e['segment_index'])
  if key not in selected:selected[key]={'u':e['u'],'v':e['v'],'a':graph['nodes'][e['u']],'b':graph['nodes'][e['v']],'tags':attrs[e['way_id']],'edges':[]}
  selected[key]['edges'].append(dict(e))
 return list(selected.values())

def goal_connected_nodes(graph):
 """Directed strict-road reachability: disconnected islands remain initial access.

 This is a connectivity filter, not a promise of a legal route: the route search
 still enforces turn restrictions. No blocked/service edges are used here.
 """
 from collections import defaultdict
 reverse=defaultdict(list)
 for e in graph['edges']:
  if not e.get('closed') and not e.get('blocked'):
   reverse[e['v']].append(e['u'])
 reached=set(graph['goals']);pending=list(reached)
 while pending:
  for u in reverse.get(pending.pop(),[]):
   if u not in reached:reached.add(u);pending.append(u)
 return reached
def attach_origin(graph,xy,attrs,segments,zones,radius=1000,max_snap=50):
 """Only goal-connected strict nodes absorb initial access; isolated strict islands do not."""
 strict_nodes=goal_connected_nodes(graph);oldids={e['id'] for e in graph['edges']};strict_ids=set(oldids)
 nearby=[]
 for s in segments:
  if project_segment(xy,s['a'],s['b'])[0]<=radius:
   nearby.append(s)
 # Restore only strict-policy roads previously cut by the old barrier treatment.
 restored=[]
 for s in nearby:
  if max(math.dist(xy,s['a']),math.dist(xy,s['b']))>radius or ORIGINAL_POLICY(s['tags'])!='allowed':continue
  for e in s['edges']:
   if e['id'] in oldids or e.get('blocked'):continue
   graph['nodes'].setdefault(s['u'],s['a']);graph['nodes'].setdefault(s['v'],s['b'])
   core=cost_geometry(dict(e),graph['nodes'],s['tags'],zones);core['strict_access_restored']=True;core['initial_access_only']=False
   graph['edges'].append(core);oldids.add(e['id']);strict_ids.add(e['id']);restored.append(e['id']);attrs[e['way_id']]=s['tags']
 strict_nodes=goal_connected_nodes(graph)
 candidates=nearby+nearest_strict(graph,xy,attrs)
 if not candidates:raise OriginError('Tidak ada ruas jalan pada cakupan data.')
 ranked=sorted(((*project_segment(xy,s['a'],s['b']),i) for i,s in enumerate(candidates)),key=lambda x:x[0])
 gap,f,snap,index=ranked[0];selected=candidates[index];name=selected['tags'].get('name','jalan tanpa nama OSM')
 if gap>max_snap:raise OriginError(f'Ruas terdekat ({name}) masih {gap:.2f} m. Tidak dibuat sambungan lurus melintasi area yang belum diketahui.')
 # Coincident but disconnected geometries can represent a bridge or parallel facilities.
 endpoint=selected['u'] if f<1e-8 else selected['v'] if f>1-1e-8 else None
 for d,frac,p,i in ranked[1:]:
  if d>gap+.05:break
  other=candidates[i]
  if (other['edges'][0]['way_id'],other['edges'][0]['segment_index'])==(selected['edges'][0]['way_id'],selected['edges'][0]['segment_index']):continue
  other_endpoint=other['u'] if frac<1e-8 else other['v'] if frac>1-1e-8 else None
  if endpoint is None or endpoint!=other_endpoint:
   raise OriginError('Titik sama dekat dengan ruas yang tidak tersambung (mungkin beda tingkat). Geser titik ke ruas yang dimaksud, beberapa meter dari persilangan.')
 def source_edge_allowed(e):
  if not e.get('blocked',False):return True
  return endpoint is None and e['v'] not in e.get('blocked_nodes',[e['u'],e['v']])
 if not any(source_edge_allowed(e) for e in selected['edges']):raise OriginError(f'Ruas terdekat ({name}) memiliki penghalang atau pembatas akses yang belum diselesaikan. Jalan lain tidak dipilih secara diam-diam.')
 added=[]
 for s in nearby:
  # The supplemental access area is explicitly bounded; do not add long excursions.
  if max(math.dist(xy,s['a']),math.dist(xy,s['b']))>radius:continue
  attrs[s['edges'][0]['way_id']]=s['tags']
  for e in s['edges']:
   if e['id'] in oldids or e.get('blocked') or e['u'] in strict_nodes:continue
   graph['nodes'].setdefault(s['u'],s['a']);graph['nodes'].setdefault(s['v'],s['b'])
   new=cost_geometry(dict(e),graph['nodes'],s['tags'],zones);new['initial_access_only']=True
   graph['edges'].append(new);added.append(new['id']);oldids.add(new['id'])
 start=endpoint
 if start is None:
  start='__origin_snap__';graph['nodes'][start]=snap
  for e in selected['edges']:
   if not source_edge_allowed(e):continue
   dest=e['v']
   dest_xy=selected['a'] if dest==selected['u'] else selected['b']
   if e['id'] not in strict_ids and math.dist(xy,dest_xy)>radius:continue
   graph['nodes'].setdefault(dest,selected['a'] if dest==selected['u'] else selected['b'])
   partial=dict(e);partial.update(id='snap:'+e['id'],u=start,source_edge_id=e['id'],initial_access_only=e['id'] not in strict_ids)
   partial['blocked']=False
   partial['confirmed_gate']=dest=='13321512874'
   cost_geometry(partial,graph['nodes'],selected['tags'],zones)
   graph['edges'].append(partial)
 else:
  graph['nodes'].setdefault(start,snap)
 if not any(e['u']==start for e in graph['edges']):raise OriginError('Titik sudah di jalan, tetapi tidak ada arah keluar yang diizinkan dalam radius akses ini; periksa pembatas akses atau radius pencarian.')
 audit={'method':'nearest road segment with directional partial-edge start','road_name':name,'way_id':selected['edges'][0]['way_id'],'segment_index':selected['edges'][0]['segment_index'],'gap_m':gap,'snapped_xy':snap,'access_radius_m':radius,'extra_directed_edges':len(added),'strict_node_count':len(strict_nodes),'restored_strict_edges':restored,'start_on_strict_node':start in strict_nodes,'lateral_gap_cost_included':False,'scope':'Only origin access may use missing-width/local service roads. Upon reaching a strict node with directed connectivity to a hospital goal, supplemental edges cannot be used again; isolated strict islands remain origin access. Turn restrictions are enforced by the search.','limits':'Nearest road is not proof of physical access across sidewalks/walls; unknown or private gates remain excluded.'}
 audit['blocked_nearby']=[{'u':e['u'],'v':e['v'],'blocked_nodes':e.get('blocked_nodes',[]),'way_id':e['way_id'],'road_name':s['tags'].get('name','tanpa nama')} for s in nearby for e in s['edges'] if e.get('blocked')]
 return graph,start,audit

def prepare_origin(graph,xy,radius=1000,max_snap=1000):
 attrs=json.loads((BASE/'network_diy/way_attributes.json').read_text(encoding='utf-8'))
 segments=catalog_segments(xy,radius);zones=load_zones()
 extra_rules=json.loads((CAT/'turn_restrictions.json').read_text())
 rulemap={json.dumps(r,sort_keys=True):r for r in graph['turn_restrictions']+extra_rules};graph['turn_restrictions']=list(rulemap.values())
 apply_goal_overrides(graph)
 return attach_origin(graph,xy,attrs,segments,zones,radius,max_snap)
