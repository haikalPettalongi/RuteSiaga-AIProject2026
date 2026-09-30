import random
import math
import unittest
import networkx as nx
from route_network import setup,search_network
from validate_network import independent_transitions
from ambulance_router import edge_cost

class IndependentTests(unittest.TestCase):
    def test_random_turn_graphs(self):
        rng=random.Random(721)
        for _ in range(25):
            nodes={str(i):[rng.random()*1000,rng.random()*1000] for i in range(10)}
            edges=[]
            for u in nodes:
                for v in nodes:
                    if u!=v and rng.random()<.22:
                        eid=f'{u}-{v}'
                        edges.append({'id':eid,'u':u,'v':v,'way_id':eid,'length_m':math.dist(nodes[u],nodes[v]),'highway':'primary'})
            rules=[]
            for e in edges:
                outs=[f for f in edges if f['u']==e['v']]
                if outs and rng.random()<.3:
                    f=rng.choice(outs)
                    rules.append({'via':e['v'],'from_way':e['way_id'],'to_way':f['way_id'],'restriction':rng.choice(['no_right_turn','only_right_turn'])})
            data={'nodes':nodes,'edges':edges,'turn_restrictions':rules}
            oracle,lookup,outgoing=independent_transitions(data)
            costs={eid:sum(edge_cost(e,'pagi').values()) for eid,e in lookup.items()}
            # Add independent start/terminal nodes with standard forward weights.
            for a,b in oracle.edges: oracle[a][b]['weight']=costs[b]
            oracle.add_node('START');oracle.add_node('GOAL')
            for e in edges:
                if e['u']=='0':oracle.add_edge('START',e['id'],weight=costs[e['id']])
                if e['v'] in {'8','9'}:oracle.add_edge(e['id'],'GOAL',weight=0)
            try:expected=nx.shortest_path_length(oracle,'START','GOAL',weight='weight')
            except nx.NetworkXNoPath:expected=None
            for a in ['astar','ucs']:
                res=search_network(setup(data),'0',['8','9'],a)
                if expected is None:self.assertIsNone(res['cost_s'])
                else:self.assertAlmostEqual(res['cost_s'],expected)

if __name__=='__main__':unittest.main()
