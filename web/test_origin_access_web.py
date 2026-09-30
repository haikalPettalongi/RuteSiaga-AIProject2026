import unittest,copy,json
import server
from origin_access_web import attach_origin,goal_connected_nodes

def edge(u,v,i):
 return dict(id=i,u=u,v=v,way_id=i,segment_index=0,direction=1,length_m=10,highway='residential',speed_kmh=20,signal_at_end=False,rail_at_end=False)
def segment(u,v,a,b,i,blocked=False):
 e=edge(u,v,i);e['blocked']=blocked
 return dict(u=u,v=v,a=a,b=b,tags={'highway':'residential','name':'Test'},edges=[e])
class AccessTests(unittest.TestCase):
 def test_default_access_rejects_beyond_one_kilometer(self):
  g={'nodes':{'m':[2000,0],'goal':[2100,0]},'edges':[edge('m','goal','main')],'goals':['goal']}
  attrs={'main':{'highway':'residential','name':'Main'}}
  segs=[segment('o','m',[0,0],[2000,0],'connector')]
  with self.assertRaises(server.OriginError):
   attach_origin(copy.deepcopy(g),[0,0],dict(attrs),segs,{})
  mapped,start,audit=attach_origin(copy.deepcopy(g),[0,0],dict(attrs),segs,{},radius=5000)
  self.assertEqual(audit['access_radius_m'],5000)
  self.assertTrue(any(e['u']==start and e['v']=='m' for e in mapped['edges']))
 def test_named_place_beyond_old_fifty_meter_limit(self):
  result=server.calculate({'lat':-7.79334345,'lon':110.3666525377634,'scenario':'siang'})
  self.assertGreater(result['gap_m'],50)
  self.assertLess(result['gap_m'],1000)
  self.assertTrue(result['hospital'])
  self.assertAlmostEqual(result['algorithms'][0]['cost_s'],result['algorithms'][1]['cost_s'])
  self.assertNotEqual(result['origin_xy'],result['snap_xy'])
 def test_island_connector_and_no_exit_after_core(self):
  g={'nodes':{'a':[0,0],'b':[10,0],'c':[20,0],'goal':[30,0]},'edges':[edge('a','b','island'),edge('c','goal','core')],'goals':['goal']}
  attrs={k:{'highway':'residential','name':'Test'} for k in ['island','core']}
  segs=[segment('b','c',[10,0],[20,0],'connector'),segment('c','z',[20,0],[20,10],'forbidden_after_core'),segment('b','x',[10,0],[10,10],'blocked',True),segment('b','far',[10,0],[20000,0],'outside_radius')]
  self.assertEqual(goal_connected_nodes(g),{'c','goal'})
  g,start,audit=attach_origin(g,[0,0],attrs,segs,{},radius=1000)
  ids={e['id'] for e in g['edges']}
  self.assertIn('connector',ids)
  self.assertNotIn('forbidden_after_core',ids)
  self.assertNotIn('blocked',ids)
  self.assertNotIn('outside_radius',ids)
  self.assertFalse(any(e['u']=='c' and e['v']=='b' for e in g['edges']))
 def test_goal_disconnected_by_oneway(self):
  g={'edges':[edge('goal','island','wrongway')],'goals':['goal']}
  self.assertEqual(goal_connected_nodes(g),{'goal'})
if __name__=='__main__':unittest.main()
