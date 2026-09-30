"""Regression and independent NetworkX checks for general origin access."""
import copy,json,math,gc
from pathlib import Path
import networkx as nx
from projection_diy import Transformer
from origin_access import prepare_origin,catalog_segments
from build_access_catalog import ORIGINAL_POLICY
from route_network import setup,search_network
from ambulance_router import edge_cost,VMAX
from validate_network import independent_transitions
BASE=Path(__file__).resolve().parent;OUT=BASE/'network_diy_akses_umum'
CASES=[('UGM',-7.773595801763427,110.376947373952),('Grafika',-7.76605243409807,110.37392217015598),('Tentara Pelajar',-7.783391923119533,110.36085404109025)]
def main():
 reports=[];t=Transformer.from_crs(4326,32749,always_xy=True)
 for name,lat,lon in CASES:
  print('Memeriksa lokasi:',name,flush=True)
  strict=json.loads((BASE/'network_diy/graph_diy_poi.json').read_text(encoding='utf-8'));old_nodes=dict(strict['nodes']);old_edges={e['id']:dict(e) for e in strict['edges']};old_goals=set(strict['goals'])
  xy=t.transform(lon,lat)
  tags_by_way={s['edges'][0]['way_id']:s['tags'] for s in catalog_segments(xy,1000)}
  graph,start,audit=prepare_origin(strict,xy)
  assert all(graph['nodes'][n]==p for n,p in old_nodes.items())
  edge_by_id={e['id']:e for e in graph['edges']};assert all(edge_by_id[k]==v for k,v in old_edges.items())
  assert old_goals<=set(graph['goals'])
  for e in graph['edges']:
   if e['id'] in old_edges:continue
   assert e.get('strict_access_restored') or e['u'] not in old_nodes
   if e.get('strict_access_restored'):assert ORIGINAL_POLICY(tags_by_way[e['way_id']])=='allowed'
   assert e['length_m']>0 and math.isclose(e['length_m'],math.dist(graph['nodes'][e['u']],graph['nodes'][e['v']]),abs_tol=1e-7)
   assert not e.get('blocked')
  state,byid,outgoing=independent_transitions(graph);targets=[eid for eid,e in byid.items() if e['v'] in graph['goals']]
  outcomes=[]
  for scenario in ['pagi','siang','sore','malam']:
   costs={eid:sum(edge_cost(e,scenario).values()) for eid,e in byid.items()}
   oracle=nx.multi_source_dijkstra_path_length(state.reverse(copy=False),targets,weight=lambda u,v,d:costs[u])
   expected=0 if start in graph['goals'] else min((costs[e['id']]+oracle.get(e['id'],math.inf) for e in outgoing[start]),default=math.inf)
   prepared=setup(graph,scenario)
   for alg in ['ucs','astar']:
    r=search_network(prepared,start,graph['goals'],alg)
    assert (r['cost_s'] is None) if math.isinf(expected) else math.isclose(expected,r['cost_s'],abs_tol=1e-6)
    core_nodes=set(old_nodes)|{e[k] for e in graph['edges'] if e.get('strict_access_restored') for k in ('u','v')}
    entered=start in core_nodes
    for eid in r.get('edges',[]):
     e=byid[eid]
     if entered:assert not e.get('initial_access_only',False)
     entered=entered or e['v'] in core_nodes
     hu=min(math.dist(graph['nodes'][e['u']],graph['nodes'][n]) for n in graph['goals'])/VMAX
     hv=min(math.dist(graph['nodes'][e['v']],graph['nodes'][n]) for n in graph['goals'])/VMAX
     assert hu<=costs[eid]+hv+1e-7
    outcomes.append({'scenario':scenario,'algorithm':alg,'cost_s':r['cost_s'],'goal':r['goal'],'hospitals':graph['goal_hospitals'].get(r['goal'],[]),'expanded_states':r['expanded_states']})
  reports.append({'name':name,'lat':lat,'lon':lon,'mapping':audit,'results':outcomes})
  print(name,'PASS',flush=True)
  del state,prepared,oracle,graph,strict,byid,edge_by_id,old_edges,outgoing;gc.collect()
 result={'passed':True,'locations':len(reports),'searches_verified':sum(len(r['results']) for r in reports),'oracle':'Independent NetworkX incoming-edge state graph','checks':['all original road nodes/edges/costs and goals retained','no return to supplemental roads after strict network entry','partial-edge geometry and positive cost','turn-aware results equal oracle in all four scenarios','heuristic consistency along resulting routes'],'cases':reports}
 (OUT/'validation_general_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print('PASS',result['searches_verified'],'searches',flush=True)
if __name__=='__main__':main()
