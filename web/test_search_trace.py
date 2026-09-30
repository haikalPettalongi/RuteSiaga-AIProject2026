import unittest
import server
from route_network import search_network
class TraceTests(unittest.TestCase):
 def test_trace_does_not_change_search(self):
  nodes={'s':[0,0],'a':[1,0],'g':[2,0]}
  edges={}
  adj={k:[] for k in nodes}
  for i,(u,v,cost) in enumerate([('s','g',4),('s','a',1),('a','g',1)]):
   e=dict(id=str(i),u=u,v=v,way_id=str(i));edges[e['id']]=e;adj[u].append((e,cost,{'base_s':cost}))
  prepared=(nodes,adj,edges,{})
  for alg in ['ucs','astar']:
   plain=search_network(prepared,'s',['g'],alg);trace=[]
   traced=search_network(prepared,'s',['g'],alg,on_expand=lambda *x:trace.append(x))
   self.assertEqual(plain['cost_s'],traced['cost_s']);self.assertEqual(plain['edges'],traced['edges'])
   self.assertEqual(len(trace),traced['expanded_states']);self.assertEqual(trace[0][0],'s');self.assertEqual(trace[-1][0],'g')
   self.assertEqual(trace[-1][2],traced['cost_s'])
if __name__=='__main__':unittest.main()
