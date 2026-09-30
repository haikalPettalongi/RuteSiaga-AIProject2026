"""Audit graf nyata dan pembanding NetworkX pada graf state ruas masuk."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random
import networkx as nx
from ambulance_router import edge_cost
from build_network_offline import directions,road_policy
from route_network import setup,search_network

BASE=Path(__file__).parent/'network_diy'


def independent_transitions(data):
    # Implementasi pembanding terpisah; tidak memanggil permitted() mesin pencarian.
    edge_by_id={e['id']:e for e in data['edges']}
    incoming=defaultdict(list);outgoing=defaultdict(list);rules=defaultdict(list)
    for e in data['edges']:
        incoming[e['v']].append(e);outgoing[e['u']].append(e)
    for rule in data['turn_restrictions']:
        rules[(rule['via'],rule['from_way'])].append(rule)
    state_graph=nx.DiGraph();state_graph.add_nodes_from(edge_by_id)
    for via,ins in incoming.items():
        for previous in ins:
            applicable=rules.get((via,previous['way_id']),[])
            for following in outgoing[via]:
                allowed=True
                for r in applicable:
                    is_target=following['way_id']==r['to_way']
                    if r['restriction'] in {'no_u_turn','only_u_turn'} and r['from_way']==r['to_way']:
                        is_target=is_target and following['v']==previous['u']
                    if (r['restriction'].startswith('only_') and not is_target) or (r['restriction'].startswith('no_') and is_target):
                        allowed=False;break
                if allowed: state_graph.add_edge(previous['id'],following['id'])
    return state_graph,edge_by_id,outgoing


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--poi',action='store_true');args=parser.parse_args()
    suffix='_poi' if args.poi else ''
    data=json.loads((BASE/('graph_diy'+suffix+'.json')).read_text(encoding='utf-8'))
    attrs=json.loads((BASE/'way_attributes.json').read_text(encoding='utf-8'))
    raw=json.loads((BASE/'network_extract.json').read_text(encoding='utf-8'))
    source_ways={w['id']:w['refs'] for w in raw['ways']}
    nodes=data['nodes'];goals=set(data['goals']);assert goals
    actual=defaultdict(set)
    for e in data['edges']:
        assert road_policy(attrs[e['way_id']])=='allowed'
        assert e['direction'] in directions(attrs[e['way_id']])
        assert math.isfinite(e['length_m']) and e['length_m']>0
        assert math.isclose(e['length_m'],math.dist(nodes[e['u']],nodes[e['v']]),abs_tol=1e-8)
        refs=source_ways[e['way_id']];j=e['segment_index']
        expected_pair=(str(refs[j]),str(refs[j+1])) if e['direction']==1 else (str(refs[j+1]),str(refs[j]))
        assert (e['u'],e['v'])==expected_pair
        actual[(e['way_id'],e['segment_index'])].add(e['direction'])
    # maxspeed yang tidak terbaca boleh menggugurkan salah satu arah; tidak boleh menambah arah.
    graph,edge_by_id,outgoing=independent_transitions(data)
    targets=[eid for eid,e in edge_by_id.items() if e['v'] in goals]
    assert targets
    rng=random.Random(20260922)
    starts=rng.sample(sorted(nodes),min(12,len(nodes)))
    starts+=sorted(goals)[:2]
    results=[];first_route=None
    for scenario in ['pagi','siang','sore','malam']:
        print('Validasi skenario:',scenario,flush=True)
        costs={eid:sum(edge_cost(e,scenario).values()) for eid,e in edge_by_id.items()}
        if args.poi:
            assert all(math.isclose(costs[eid],e['scenario_cost_s'][scenario],rel_tol=1e-12,abs_tol=1e-9) for eid,e in edge_by_id.items())
        # Reversed arc b->a carries original transition a->b cost (cost of edge b).
        oracle=nx.multi_source_dijkstra_path_length(graph.reverse(copy=False),targets,weight=lambda u,v,d:costs[u])
        prepared=setup(data,scenario)
        for start in starts:
            expected=0 if start in goals else min((costs[e['id']]+oracle.get(e['id'],math.inf) for e in outgoing[start]),default=math.inf)
            pair=[search_network(prepared,start,goals,a) for a in ['ucs','astar']]
            for res in pair:
                if math.isinf(expected): assert res['cost_s'] is None
                else: assert math.isclose(res['cost_s'],expected,rel_tol=1e-10,abs_tol=1e-6),(scenario,start,res['cost_s'],expected)
                if res.get('edges'):
                    assert res['nodes'][0]==start and res['goal'] in goals
                    assert all(graph.has_edge(a,b) for a,b in zip(res['edges'],res['edges'][1:]))
                    assert math.isclose(sum(costs[x] for x in res['edges']),res['cost_s'],abs_tol=1e-6)
                    if first_route is None:
                        first_route={'scenario':scenario,'start':start,**res,'hospital_names':data['goal_hospitals'][res['goal']]}
            results.append({'scenario':scenario,'start':start,'expected_s':None if math.isinf(expected) else expected,'ucs_ms':pair[0]['runtime_ms'],'astar_ms':pair[1]['runtime_ms'],'ucs_states':pair[0]['expanded_states'],'astar_states':pair[1]['expanded_states']})
    report={'passed':True,'query_pairs':len(results),'search_runs':len(results)*2,'oracle':'NetworkX reverse multi-source Dijkstra on independently constructed incoming-edge state graph','seed':20260922,'unreachable_queries':sum(r['expected_s'] is None for r in results),'checks':['allowed highway and access policy','oneway including reverse and roundabout','positive metric segment lengths','endpoint references','turn-valid paths','cost equality with independent oracle'],'cost_limit':data['cost_status'],'results':results}
    (BASE/('validation'+suffix+'_report.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    (BASE/('example'+suffix+'_route.json')).write_text(json.dumps(first_route,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS',len(results),'kueri berpasangan',flush=True)


if __name__=='__main__': main()
