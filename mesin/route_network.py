"""A*/UCS dengan state ruas masuk untuk mematuhi relasi larangan belok."""
import argparse
from collections import defaultdict
import heapq
import itertools
import json
import math
from pathlib import Path
import time
from ambulance_router import prepare, VMAX


def setup(data,scenario='pagi'):
    unrestricted={**data,'turn_restrictions':[]}
    nodes,adj=prepare(unrestricted,scenario)
    edges={e['id']:e for e in data['edges']}
    rules=defaultdict(list)
    for r in data.get('turn_restrictions',[]):
        rules[(r['via'],r['from_way'])].append(r)
    return nodes,adj,edges,rules


def permitted(incoming,outgoing,rules):
    if incoming is None: return True
    for rule in rules.get((outgoing['u'],incoming['way_id']),[]):
        kind=rule['restriction']; same_way=outgoing['way_id']==rule['to_way']
        if kind.endswith('u_turn') and rule['from_way']==rule['to_way']:
            matches=same_way and outgoing['v']==incoming['u']
        else: matches=same_way
        if kind.startswith('no_') and matches: return False
        if kind.startswith('only_') and not matches: return False
    return True


def search_network(prepared,start,goals,algorithm='astar',diagnostics=False,on_expand=None):
    nodes,adj,edges,rules=prepared; goals=set(goals)
    if algorithm not in {'astar','ucs'}: raise ValueError('Algoritma invalid')
    if start not in nodes or not goals or not goals<=nodes.keys(): raise ValueError('Start/goal invalid')
    tick=time.perf_counter();counter=itertools.count();heuristic={}
    def h(n):
        if algorithm=='ucs': return 0
        if n not in heuristic: heuristic[n]=min(math.dist(nodes[n],nodes[g]) for g in goals)/VMAX
        return heuristic[n]
    root=(start,None);best={root:0.0};parent={};heap=[(h(start),next(counter),0.0,root)];expanded=0;peak=1
    while heap:
        _,_,cost,state=heapq.heappop(heap)
        if cost!=best[state]: continue
        u,incoming=state;expanded+=1
        if on_expand is not None: on_expand(u,incoming,cost)
        if u in goals:
            seq=[]; parts=dict.fromkeys(['base_s','poi_s','signal_s','rail_s'],0.0)
            cursor=state
            while cursor!=root:
                prev,eid,comp=parent[cursor];seq.append(eid)
                for k,val in comp.items(): parts[k]=parts.get(k,0)+val
                cursor=prev
            seq.reverse()
            return {'algorithm':algorithm,'goal':u,'cost_s':cost,'edges':seq,'nodes':[start]+[edges[e]['v'] for e in seq],**parts,'expanded_states':expanded,'peak_heap_entries':peak,'runtime_ms':(time.perf_counter()-tick)*1000}
        for edge,weight,comp in adj[u]:
            if not permitted(edges.get(incoming),edge,rules): continue
            new=(edge['v'],edge['id']);trial=cost+weight
            if trial<best.get(new,math.inf):
                best[new]=trial;parent[new]=(state,edge['id'],comp)
                heapq.heappush(heap,(trial+h(new[0]),next(counter),trial,new))
        peak=max(peak,len(heap))
    result={'algorithm':algorithm,'goal':None,'cost_s':None,'status':'unreachable','expanded_states':expanded,'runtime_ms':(time.perf_counter()-tick)*1000}
    if diagnostics:result['_reachable_nodes']=list({state[0] for state in best})
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--graph',default=str(Path(__file__).parent/'network_diy'/('graph_diy_poi.json' if (Path(__file__).parent/'network_diy/graph_diy_poi.json').exists() else 'graph_diy.json')));p.add_argument('--start',required=True);p.add_argument('--scenario',choices=['pagi','siang','sore','malam'],default='pagi');args=p.parse_args()
    data=json.loads(Path(args.graph).read_text(encoding='utf-8'));prepared=setup(data,args.scenario)
    print(json.dumps([search_network(prepared,args.start,data['goals'],a) for a in ['ucs','astar']],indent=2))
