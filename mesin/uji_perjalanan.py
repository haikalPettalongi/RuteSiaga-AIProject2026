"""CLI rute: jaringan ketat atau akses awal umum dengan snap ke ruas jalan."""
import argparse,json,math
from pathlib import Path
from datetime import datetime,timezone
from projection_diy import Transformer
from route_network import setup,search_network
from origin_access import prepare_origin,OriginError
from ambulance_router import edge_cost
BASE=Path(__file__).resolve().parent

def save_result(directory,scenario,payload):
 directory.mkdir(parents=True,exist_ok=True)
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
 text=json.dumps(payload,ensure_ascii=False,indent=2)
 archive=directory/f'perjalanan_{scenario}_{stamp}.json';archive.write_text(text,encoding='utf-8')
 latest=directory/f'hasil_perjalanan_{scenario}.json';temp=latest.with_suffix('.tmp');temp.write_text(text,encoding='utf-8');temp.replace(latest)
 print('Rincian tersimpan di: '+str(latest));return latest

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--lat',type=float,required=True);p.add_argument('--lon',type=float,required=True)
 p.add_argument('--scenario',choices=['pagi','siang','sore','malam'],default='pagi')
 p.add_argument('--variant',choices=['ketat','akses-awal'],default='akses-awal')
 p.add_argument('--access-radius',type=float,default=1000,help='Radius jalan penghubung awal dalam meter; default 1000')
 p.add_argument('--check',action='store_true')
 a=p.parse_args()
 if not (math.isfinite(a.lat) and math.isfinite(a.lon) and -90<=a.lat<=90 and -180<=a.lon<=180):p.error('Koordinat tidak valid')
 if not math.isfinite(a.access_radius) or not 50<=a.access_radius<=5000:p.error('Radius akses harus 50 sampai 5000 meter')
 directory=BASE.parent/'hasil/json_terminal'
 payload={'variant':a.variant,'input_latlon':[a.lat,a.lon],'scenario':a.scenario,'scope':'Estimated time to hospital road proxies, not measured ETA; lateral snap gap excluded'}
 print('Membaca graf DIY: '+a.variant,flush=True)
 graph=json.loads((BASE/'network_diy/graph_diy_poi.json').read_text(encoding='utf-8'))
 xy=Transformer.from_crs(4326,32749,always_xy=True).transform(a.lon,a.lat)
 try:
  if a.variant=='akses-awal':
   graph,node,audit=prepare_origin(graph,xy,radius=a.access_radius)
   gap=audit['gap_m'];payload['origin_mapping']=audit
   print(f"Ruas awal: {audit['road_name']}; jarak ke ruas: {gap:.2f} meter.",flush=True)
   print(f"Akses awal dibatasi radius {a.access_radius:g} m; setelah masuk jaringan utama, aturan lebar tetap berlaku.",flush=True)
  else:
   node=min(graph['nodes'],key=lambda n:math.dist(xy,graph['nodes'][n]));gap=math.dist(xy,graph['nodes'][node])
   print(f'Titik jalan awal: {node}; selisih dari koordinat: {gap:.2f} meter.',flush=True)
   if gap>50:raise OriginError('Jarak ke node lebih dari 50 m. Coba --variant akses-awal untuk pemetaan ke ruas dan penghubung awal.')
   if not any(e['u']==node for e in graph['edges']):raise OriginError('Tidak ada ruas keluar yang diizinkan pada node awal.')
  payload.update(start_node=node,start_gap_m=gap)
 except OriginError as exc:
  payload.update(status='origin_mapping_requires_review',message=str(exc),results=[])
  print('Pemetaan awal belum dapat digunakan: '+str(exc),flush=True)
  save_result(directory,a.scenario,payload);return
 print('Pemetaan geometris belum memverifikasi sisi jalan atau akses fisik.',flush=True)
 if a.check:
  payload.update(status='origin_mapping_checked',results=[]);save_result(directory,a.scenario,payload);return
 print('Menghitung UCS dan A*...',flush=True)
 prepared=setup(graph,a.scenario);byid=prepared[2]
 results=[search_network(prepared,node,graph['goals'],alg,diagnostics=a.variant=='akses-awal') for alg in ['ucs','astar']]
 for r in results:
  reached=set(r.pop('_reachable_nodes',[]))
  if r['cost_s'] is None and a.variant=='akses-awal':
   frontier=[b for b in audit.get('blocked_nearby',[]) if b['u'] in reached]
   r['blocked_frontier']=frontier
   if frontier:print('Ada penghalang pada ruas keluar yang terjangkau: '+', '.join(sorted({n for b in frontier for n in b['blocked_nodes']})))
  if r['cost_s'] is None:
   print(r['algorithm'].upper()+': tidak ada rute.');continue
  r['hospitals']=graph['goal_hospitals'][r['goal']]
  override=next((h for h in graph.get('hospital_goal_overrides',[]) if h['road_node']==r['goal']),None)
  if override:r['destination_scope']=override['goal_kind']
  es=[byid[eid] for eid in r['edges']]
  r['distance_m']=sum(e['length_m'] for e in es)
  r['confirmed_grafika_gate_used']=any(e.get('confirmed_gate',False) for e in es)
  r['route_xy']=[graph['nodes'][n] for n in r['nodes']]
  r['route_edges']=[{**e,'components_s':edge_cost(e,a.scenario)} for e in es]
  print(f"{r['algorithm'].upper()}: {', '.join(r['hospitals'])} | {r['distance_m']:.0f} m | {r['cost_s']:.1f} detik ({r['cost_s']/60:.2f} menit) | komputasi {r['runtime_ms']:.1f} ms")
 assert (results[0]['cost_s'] is None)==(results[1]['cost_s'] is None)
 if results[0]['cost_s'] is not None:
  assert math.isclose(results[0]['cost_s'],results[1]['cost_s'],abs_tol=1e-6)
  print('Pemeriksaan: biaya A* dan UCS sama.')
 else:
  print('Tidak ada jalur yang memenuhi arah, akses, penghalang dan aturan jaringan pada radius akses ini. Ini bukan bukti tidak ada jalan di lapangan.')
 if results[0].get('gate_s',0):print(f"Asumsi waktu tunggu gerbang pada rute: {results[0]['gate_s']:.0f} detik (belum dikalibrasi).")
 if any(r.get('confirmed_grafika_gate_used') for r in results):print('Rute memakai gerbang Grafika yang dikonfirmasi dapat dilewati; waktu tunggu diasumsikan 0 detik.')
 if any(r.get('destination_scope')=='public_road_junction_at_inbound_hospital_access' for r in results):print('Tujuan Sardjito: simpang akses masuk di jalan umum; perjalanan di dalam kompleks belum dihitung.')
 payload.update(status='ok' if results[0]['cost_s'] is not None else 'unreachable_under_model',results=results)
 save_result(directory,a.scenario,payload)
 print('Waktu merupakan estimasi skenario, belum dikalibrasi dengan perjalanan nyata.')
if __name__=='__main__':main()
