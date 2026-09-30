"""Local-only single-page UI for the existing DIY ambulance routing engine."""
import copy,gzip,json,math,sys,threading,time,traceback,webbrowser,argparse,sqlite3
from pathlib import Path
from http import HTTPStatus
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parent
CONFIG=json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig'))
ENGINE=(ROOT/CONFIG['engine_dir']).resolve()
sys.path.insert(0,str(ENGINE))
from projection_diy import forward,inverse
from origin_access_web import prepare_origin,catalog_segments,OriginError
from route_network import setup,search_network
from hospital_goal_overrides import apply_goal_overrides
from location_search import search as search_locations
from compact_catalog import available as compact_available,query as compact_query
GRAPH=None
LOCK=threading.Lock()
LOAD_LOCK=threading.Lock()

def load_graph():
 packed=ENGINE/'network_diy/graph_diy_poi.json.zst'
 if packed.exists():
  from compression import zstd
  return json.loads(zstd.decompress(packed.read_bytes()))
 return json.loads((ENGINE/'network_diy/graph_diy_poi.json').read_text(encoding='utf-8'))

def base_graph():
 global GRAPH
 if GRAPH is None:
  with LOAD_LOCK:
   if GRAPH is None:GRAPH=load_graph()
 return GRAPH

def warm_up():
 # Load the ~160 MB graph in the background so the first search does not stall.
 try:base_graph()
 except Exception:traceback.print_exc()

def map_segments(center,radius,overview=False):
 if not overview:return catalog_segments(center,radius)
 # Read only major roads at wider zooms, keeping the entire viewport covered.
 CAT=ENGINE/'network_diy_akses_umum'
 if compact_available(CAT):return compact_query(CAT,center,radius,major_only=True)
 path=CAT/'access_catalog.sqlite'
 x,y=center
 with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
  rows=db.execute("SELECT s.payload FROM segments s JOIN bounds b ON b.id=s.id WHERE b.minx<=? AND b.maxx>=? AND b.miny<=? AND b.maxy>=? AND json_extract(s.payload,'$.tags.highway') IN ('motorway','motorway_link','trunk','trunk_link','primary','primary_link','secondary','secondary_link','tertiary','tertiary_link')",(x+radius,x-radius,y+radius,y-radius))
  return [json.loads(r[0]) for r in rows]

def road_map(center,radius=1800,overview=False):
 roads=[];labels={}
 for s in map_segments(center,radius,overview):
  name=s['tags'].get('name','');kind=s['tags'].get('highway','');a,b=s['a'],s['b']
  roads.append({'a':a,'b':b,'major':kind in ['primary','secondary','tertiary','trunk'],'blocked':all(e.get('blocked') for e in s['edges'])})
  if name and kind in ['primary','secondary','tertiary','trunk']:
   mid=[(a[0]+b[0])/2,(a[1]+b[1])/2];dist=math.dist(mid,center)
   if name not in labels or dist<labels[name]['distance']:labels[name]={'name':name,'xy':mid,'distance':dist}
 g={'nodes':base_graph()['nodes'],'edges':base_graph()['edges'],'goals':list(base_graph()['goals']),'goal_hospitals':copy.deepcopy(base_graph()['goal_hospitals'])}
 apply_goal_overrides(g)
 return {'center':center,'radius':radius,'overview':overview,'roads':roads,'labels':sorted(labels.values(),key=lambda x:x['distance'])[:80],'hospitals':[{'xy':g['nodes'][n],'name':', '.join(g['goal_hospitals'][n])} for n in g['goals'] if math.dist(g['nodes'][n],center)<radius*1.5],'goal_count':len(g['goals'])}

def calculate(data, *, include_trace=True, include_map=True):
 lat=float(data['lat']);lon=float(data['lon']);scenario=data['scenario']
 if not all(math.isfinite(v) for v in (lat,lon)) or scenario not in ['pagi','siang','sore','malam']:raise ValueError('Koordinat atau skenario tidak valid.')
 xy=forward(lon,lat);started=time.perf_counter()
 # Existing edge dictionaries are not mutated by the overlay; shallow copying preserves immutable data.
 base=base_graph();g={**base,'nodes':dict(base['nodes']),'edges':list(base['edges']),'goals':list(base['goals']),'goal_hospitals':copy.deepcopy(base['goal_hospitals']),'turn_restrictions':list(base['turn_restrictions'])}
 g,start,audit=prepare_origin(g,xy)
 prepared=setup(g,scenario);results=[];traces=[]
 for algorithm in ['ucs','astar']:
  steps=[];total=0;last=None
  def record(node,incoming,cost):
   nonlocal total,last
   total+=1
   edge=prepared[2].get(incoming)
   last={'xy':g['nodes'][node],'from_xy':g['nodes'][edge['u']] if edge else None,'cost_s':cost,'step':total}
   if len(steps)<10000:steps.append(last)
  result=search_network(prepared,start,g['goals'],algorithm,on_expand=record if include_trace else None)
  if total>len(steps):steps[-1]=last
  results.append(result)
  if include_trace:traces.append({'algorithm':algorithm,'steps':steps,'total':total,'truncated':total>len(steps)})
 if any(r['cost_s'] is None for r in results):raise OriginError('Tidak ditemukan rute sesuai aturan akses, arah, gerbang, dan radius penghubung awal 1 km. Coba titik lain pada jalan kendaraan; jangan menganggap ruas ini pasti tidak dapat dilalui di lapangan.')
 if not math.isclose(results[0]['cost_s'],results[1]['cost_s'],abs_tol=1e-6):raise RuntimeError('Pemeriksaan biaya kedua algoritma tidak cocok.')
 edges=prepared[2];r=results[0];path=[g['nodes'][n] for n in r['nodes']];goal=r['goal']
 lines=[]
 for item in results:
  lines.append({k:item[k] for k in ['algorithm','cost_s','runtime_ms','expanded_states']})
 comps={k:r.get(k,0) for k in ['base_s','poi_s','signal_s','rail_s','gate_s']}
 distance=sum(edges[e]['length_m'] for e in r['edges'])
 result={'hospital':', '.join(g['goal_hospitals'][goal]),'goal_xy':g['nodes'][goal],'origin_xy':xy,'snap_xy':g['nodes'][start],'road_name':audit['road_name'],'gap_m':audit['gap_m'],'distance_m':distance,'cost_s':r['cost_s'],'scenario':scenario,'path':path,'alternate_path':[g['nodes'][n] for n in results[1]['nodes']],'same_path':results[0]['edges']==results[1]['edges'],'algorithms':lines,'components':comps,'goal_count':len(g['goals']),'total_processing_s':time.perf_counter()-started,'scope':'Estimasi ke titik jalan RS; akses dalam kompleks dan selisih ke ruas belum dihitung.','gate_confirmed_used':any(edges[e].get('confirmed_gate') for e in r['edges'])}
 center=[(min(p[0] for p in path)+max(p[0] for p in path))/2,(min(p[1] for p in path)+max(p[1] for p in path))/2]
 extent=max(max(p[0] for p in path)-min(p[0] for p in path),max(p[1] for p in path)-min(p[1] for p in path))
 if include_map:result['map']=road_map(center,min(4000,max(1000,extent*.65+250)))
 if include_trace:result['traces']=traces
 return result

STATIC={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
HEADERS=[('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')]

def origin_ok(origin,host):
 if origin is None:return True
 port=CONFIG.get('port',8765)
 return urlparse(origin).netloc in {host,f'127.0.0.1:{port}',f'localhost:{port}'}

def dispatch(method,raw_path,body,origin=None,host=None):
 """Return (status, payload, content_type). Payload is a dict for JSON or bytes for static files."""
 path=urlparse(raw_path).path
 if method=='GET':
  if path=='/api/health':return 200,{'ok':True,'ready':GRAPH is not None},None
  if path=='/api/bootstrap':
   try:return 200,road_map(forward(110.376947373952,-7.773595801763427)),None
   except Exception:traceback.print_exc();return 503,{'error':'Data peta belum dapat dibaca. Periksa lokasi mesin dan data pada config.json.'},None
  if path not in STATIC:return 404,{'error':'Tidak ditemukan'},None
  name,kind=STATIC[path];return 200,(ROOT/'dist'/name).read_bytes(),kind
 if method!='POST':return 405,{'error':'Metode tidak didukung'},None
 if not origin_ok(origin,host):return 403,{'error':'Origin ditolak'},None
 try:
  if not 0<len(body)<=4096:raise ValueError('Ukuran permintaan tidak valid')
  data=json.loads(body)
  if path=='/api/map-view':
   x,y,w,h=(float(data[k]) for k in ('x','y','width','height'))
   if not all(math.isfinite(v) for v in (x,y,w,h)) or not (0<w<=100000 and 0<h<=100000):raise ValueError('Ukuran tampilan peta tidak valid.')
   lon,lat=inverse(x,y);forward(lon,lat)
   radius=max(w,h)*.65
   return 200,road_map((x,y),max(500,radius),max(w,h)>6500),None
  if path=='/api/locations':return 200,search_locations(ENGINE,ROOT/'locations_index.json',data.get('query','')),None
  if path=='/api/map':
   xy=forward(float(data['lon']),float(data['lat']))
   return 200,{'xy':xy,'map':road_map(xy,1800)},None
  if path=='/api/coordinate':
   x,y=float(data['x']),float(data['y']);lon,lat=inverse(x,y);return 200,{'lat':lat,'lon':lon},None
  if path!='/api/route':return 404,{'error':'Tidak ditemukan'},None
  if not LOCK.acquire(blocking=False):return 409,{'error':'Perhitungan lain masih berjalan. Tunggu sebentar.'},None
  try:result=calculate(data)
  finally:LOCK.release()
  return 200,result,None
 except (OriginError,ValueError,KeyError,TypeError) as e:return 422,{'error':str(e)},None
 except Exception:
  traceback.print_exc();return 500,{'error':'Mesin rute mengalami masalah. Lihat catatan server untuk rinciannya.'},None

def encode(payload,ctype):
 if isinstance(payload,bytes):return payload,ctype
 return json.dumps(payload,ensure_ascii=False,allow_nan=False).encode(),'application/json; charset=utf-8'

class Handler(BaseHTTPRequestHandler):
 def log_message(self,fmt,*args):print(fmt%args,flush=True)
 def reply(self,method):
  body=b''
  if method=='POST':
   try:length=int(self.headers.get('Content-Length','0'))
   except ValueError:length=0
   body=self.rfile.read(length) if 0<length<=4096 else b''
  status,payload,kind=dispatch(method,self.path,body,self.headers.get('Origin'),self.headers.get('Host'))
  data,ctype=encode(payload,kind)
  self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)))
  for k,v in HEADERS:self.send_header(k,v)
  self.end_headers();self.wfile.write(data)
 def do_GET(self):self.reply('GET')
 def do_POST(self):self.reply('POST')

def app(environ,start_response):
 """WSGI entry point (used by Vercel); the local server above shares the same dispatcher."""
 method=environ.get('REQUEST_METHOD','GET')
 try:length=int(environ.get('CONTENT_LENGTH') or 0)
 except ValueError:length=0
 body=environ['wsgi.input'].read(length) if 0<length<=4096 else b''
 raw=environ.get('PATH_INFO','/')+('?'+environ['QUERY_STRING'] if environ.get('QUERY_STRING') else '')
 origin=environ.get('HTTP_ORIGIN');host=environ.get('HTTP_X_FORWARDED_HOST') or environ.get('HTTP_HOST')
 status,payload,kind=dispatch(method,raw,body,origin,host)
 data,ctype=encode(payload,kind);extra=[('Vary','Accept-Encoding')]
 # Serverless responses are capped at ~4.5 MB; road-map JSON compresses roughly 6x.
 if len(data)>50000 and 'gzip' in environ.get('HTTP_ACCEPT_ENCODING',''):data=gzip.compress(data,5);extra.append(('Content-Encoding','gzip'))
 start_response(f'{status} {HTTPStatus(status).phrase}',[('Content-Type',ctype),('Content-Length',str(len(data))),*HEADERS,*extra])
 return [data]

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--open',action='store_true');args=p.parse_args()
 server=ThreadingHTTPServer(('127.0.0.1',CONFIG.get('port',8765)),Handler)
 url=f'http://127.0.0.1:{server.server_port}'
 threading.Thread(target=warm_up,daemon=True).start()
 print('WEB SIAP: '+url,flush=True)
 if args.open:webbrowser.open(url)
 server.serve_forever()
