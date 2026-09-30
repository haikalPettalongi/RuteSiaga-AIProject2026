"""Build a reusable DIY access-road catalog; strict network remains unchanged."""
import json,re,sqlite3,time
from pathlib import Path
from collections import Counter
from projection_diy import Transformer
from shapely.geometry import shape,LineString
from shapely.prepared import prep
import build_network_offline as b
BASE=Path(__file__).resolve().parent;OUT=BASE/'network_diy_akses_umum'
ORIGINAL_POLICY=b.road_policy

def access_policy(tags):
 if re.match(r'^(gang\b|gg\.?\s)',tags.get('name',''),re.I):return 'named_alley'
 if tags.get('service') in {'alley','parking_aisle','driveway','drive-through','emergency_access'}:return 'service_subtype_review'
 t=dict(tags)
 if t.get('highway')=='service':t['highway']='residential'
 # Missing width is unknown, not narrow. Do not change explicit limits.
 if t.get('highway') in {'residential','unclassified'} and 'width' not in t:t['width']='3'
 return ORIGINAL_POLICY(t)

GATES={'gate','swing_gate','lift_gate'}
def node_allowed(n,t):
 if not b.access_ok(t) or any('conditional' in k for k in t):return False
 if any(k in t for k in ('maxheight','maxweight','maxaxleload','maxlength')):return False
 for k in ('width','maxwidth','maxwidth:physical'):
  if k in t and (b.numeric(t[k]) is None or b.numeric(t[k])<3):return False
 barrier=t.get('barrier','no')
 if barrier in {'no','entrance','cattle_grid','toll_booth','border_control'}:return True
 if barrier not in GATES:return False
 if t.get('locked') not in (None,'no') or t.get('opening_hours') not in (None,'24/7'):return False
 # Explicit motorcar > motor_vehicle > vehicle > access permission, not barrier alone.
 access=next((t[k] for k in ('motorcar','motor_vehicle','vehicle','access') if k in t),None)
 return access in b.ALLOWED_ACCESS

def main():
 OUT.mkdir(exist_ok=True);cache=OUT/'network_extract.json'
 if cache.exists():raw=json.loads(cache.read_text(encoding='utf-8'))
 else:
  b.road_policy=access_policy
  raw=b.extract(Path(r'C:\Users\LENOVO\Downloads\java-260920.osm.pbf'),OUT)
 print('Menyusun indeks spasial akses awal...',flush=True)
 project=Transformer.from_crs(4326,32749,always_xy=True).transform
 coords={n:project(v[0],v[1]) for n,v in raw['nodes'].items()};region=prep(shape(raw['region']))
 ways={w['id']:w for w in raw['ways']};banned=set();turns=[]
 for r in raw['restrictions']:
  t=r['tags'];members=r['members'];fr=[str(mid) for mt,mid,role in members if mt==1 and role=='from'];to=[str(mid) for mt,mid,role in members if mt==1 and role=='to'];via=[str(mid) for mt,mid,role in members if mt==0 and role=='via']
  if not set(fr)&ways.keys():continue
  k=t.get('restriction:motorcar',t.get('restriction:motor_vehicle',t.get('restriction')))
  if k is None or set(t.get('except','').split(';'))&{'motorcar','motor_vehicle','vehicle'}:continue
  if len(fr)==len(to)==len(via)==1 and k in {'no_left_turn','no_right_turn','no_straight_on','no_u_turn','only_left_turn','only_right_turn','only_straight_on','only_u_turn'} and not any('conditional' in x for x in t) and not any(mt==1 and role=='via' for mt,mid,role in members):turns.append({'from_way':fr[0],'to_way':to[0],'via':via[0],'restriction':k,'osm_relation':r['id']})
  else:banned.update(fr)
 gate='13321512874';blocked={n for n,(_,_,t) in raw['nodes'].items() if not node_allowed(n,t)}
 dbpath=OUT/'access_catalog.tmp.sqlite';db=sqlite3.connect(dbpath)
 db.executescript('DROP TABLE IF EXISTS segments; DROP TABLE IF EXISTS bounds; CREATE TABLE segments(id INTEGER PRIMARY KEY,payload TEXT NOT NULL); CREATE VIRTUAL TABLE bounds USING rtree(id,minx,maxx,miny,maxy);')
 count=0;last=time.monotonic();stats=Counter()
 for wid,w in ways.items():
  if wid in banned:continue
  t=w['tags']
  for j,(u,v) in enumerate(zip(w['refs'],w['refs'][1:])):
   u,v=str(u),str(v)
   if u not in coords or v not in coords:continue
   a,c=coords[u],coords[v]
   if not region.covers(LineString([a,c])):continue
   length=((a[0]-c[0])**2+(a[1]-c[1])**2)**.5
   if length<=0:continue
   edges=[]
   for d in b.directions(t):
    fr,to=(u,v) if d==1 else (v,u);speed=b.SPEED_KMH[t['highway']]
    st=t.get('maxspeed:forward' if d==1 else 'maxspeed:backward',t.get('maxspeed'))
    if st:
     m=re.fullmatch(r'(\d+(?:\.\d+)?)\s*(km/h|mph)?',st)
     if not m:continue
     speed=min(speed,float(m[1])*(1.609344 if m[2]=='mph' else 1))
    if speed<=0:continue
    nt=raw['nodes'][to][2]
    edges.append({'id':f'{wid}:{j}:{d}','u':fr,'v':to,'way_id':wid,'segment_index':j,'direction':d,'length_m':length,'highway':t['highway'],'speed_kmh':speed,'signal_at_end':nt.get('highway')=='traffic_signals','rail_at_end':nt.get('railway')=='level_crossing' and t.get('bridge','no')=='no' and t.get('tunnel','no')=='no','blocked':u in blocked or v in blocked,'blocked_nodes':[n for n in (u,v) if n in blocked],'confirmed_gate':gate in (u,v),'gate_wait_s':(0.0 if to==gate else 10.0) if nt.get('barrier') in GATES and to not in blocked else 0.0,'gate_node_at_end':to if nt.get('barrier') in GATES else None})
   if not edges:continue
   count+=1;payload={'u':u,'v':v,'a':a,'b':c,'tags':t,'edges':edges}
   db.execute('INSERT INTO segments VALUES (?,?)',(count,json.dumps(payload,ensure_ascii=False)))
   db.execute('INSERT INTO bounds VALUES (?,?,?,?,?)',(count,min(a[0],c[0]),max(a[0],c[0]),min(a[1],c[1]),max(a[1],c[1])))
   stats['blocked_segments' if u in blocked or v in blocked else 'usable_segments']+=1
  if time.monotonic()-last>20:print('Indeks:',count,'segmen',flush=True);db.commit();last=time.monotonic()
 db.commit();db.close();dbpath.replace(OUT/'access_catalog.sqlite')
 (OUT/'turn_restrictions.json').write_text(json.dumps(turns),encoding='utf-8')
 (OUT/'catalog_report.json').write_text(json.dumps({'source':raw['source'],'source_bytes':raw['source_bytes'],'segments':count,'stats':dict(stats),'region':'DIY + 10km buffer','policy':'missing width allowed for origin access only; service except excluded subtypes; all explicit dimensions/access/direction rules preserved','confirmed_gate':gate,'gate_policy':'explicit motor-vehicle permission required; no/private/locked/unknown gates excluded; allowed gate arrival adds assumed 10 seconds, confirmed Grafika gate 0 seconds','schema_version':2,'coordinate_crs':'EPSG:32749'},indent=2),encoding='utf-8')
 print('Katalog siap:',count,flush=True)
if __name__=='__main__':main()
