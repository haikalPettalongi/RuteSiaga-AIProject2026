import unittest,copy,math
from shapely.geometry import box
from shapely import STRtree
from origin_access import attach_origin,OriginError
from route_network import setup,search_network
from build_access_catalog import access_policy,node_allowed

def edge(i,u,v,pts,**kw):
 return dict(id=i,u=u,v=v,way_id=i.split(':')[0],segment_index=0,direction=1,length_m=math.dist(pts[u],pts[v]),highway='residential',speed_kmh=36,**kw)
def segment(e,pts,**tags):
 return {'u':e['u'],'v':e['v'],'a':pts[e['u']],'b':pts[e['v']],'tags':{'highway':'residential',**tags},'edges':[e]}
def graph(pts,es,goal):return {'nodes':pts,'edges':es,'goals':[goal],'goal_hospitals':{goal:['RS']},'turn_restrictions':[]}
def run(g,start):return search_network(setup(g,'siang'),start,g['goals'],'astar')

class OriginAccessTests(unittest.TestCase):
 def test_long_oneway_snap_partial_and_signal(self):
  pts={'A':[0,0],'B':[1000,0]};e=edge('w:0:1','A','B',pts,signal_at_end=True);g=graph(pts,[e],'B');old=copy.deepcopy(g)
  g,s,a=attach_origin(g,(600,3),{'w':{}},[],{},radius=1000)
  self.assertAlmostEqual(a['gap_m'],3);self.assertAlmostEqual(run(g,s)['cost_s'],40+25)
  self.assertEqual(g['edges'][0],old['edges'][0]);self.assertEqual(g['nodes']['A'],old['nodes']['A'])
  g['goals']=['A'];self.assertIsNone(run(g,s)['cost_s'])
 def test_partial_poi_not_prorated(self):
  pts={'A':[0,0],'B':[1000,0]};e=edge('w:0:1','A','B',pts,exposure_m={'school':200});g=graph(pts,[e],'B');z=box(0,-1,200,1)
  g,s,a=attach_origin(g,(600,0),{'w':{}},[],{'school':([z],STRtree([z]))})
  self.assertEqual(run(g,s)['poi_s'],0)
 def test_no_return_to_access_after_main(self):
  pts={'M':[0,0],'G':[100,0]};main=edge('main:0:1','M','G',pts);g=graph(dict(pts),[main],'G');allpts={**pts,'O':[-100,0],'X':[50,10]}
  segs=[segment(edge(i,u,v,allpts),allpts) for i,u,v in [('a:0:1','O','M'),('b:0:1','M','X'),('c:0:1','X','G')]]
  g,s,a=attach_origin(g,(-50,0),{'main':{}},segs,{})
  self.assertNotIn('b:0:1',[e['id'] for e in g['edges']]);self.assertEqual(run(g,s)['edges'],['snap:a:0:1','main:0:1'])
 def test_nearest_blocked_is_not_silently_replaced(self):
  pts={'A':[0,10],'B':[100,10]};g=graph(pts,[edge('m:0:1','A','B',pts)],'B');p={'C':[0,0],'D':[100,0]};e=edge('x:0:1','C','D',p,blocked=True)
  with self.assertRaisesRegex(OriginError,'penghalang'):attach_origin(g,(50,0),{'m':{}},[segment(e,p)],{})
 def test_disconnected_crossing_is_ambiguous(self):
  pts={'A':[-100,0],'B':[100,0]};g=graph(pts,[edge('m:0:1','A','B',pts)],'B');p={'C':[0,-100],'D':[0,100]};e=edge('x:0:1','C','D',p)
  with self.assertRaisesRegex(OriginError,'tidak tersambung'):attach_origin(g,(0,0),{'m':{}},[segment(e,p)],{})
 def test_turn_rule_on_first_junction_survives_snap(self):
  pts={'A':[0,0],'B':[100,0],'C':[100,100]};g=graph(pts,[edge('w:0:1','A','B',pts),edge('z:0:1','B','C',pts)],'C')
  g['turn_restrictions']=[{'via':'B','from_way':'w','to_way':'z','restriction':'no_right_turn'}]
  g,s,a=attach_origin(g,(50,0),{'w':{},'z':{}},[],{})
  self.assertIsNone(run(g,s)['cost_s'])
 def test_radius_bounds_access(self):
  pts={'A':[500,0],'B':[600,0]};g=graph(pts,[edge('m:0:1','A','B',pts)],'B');p={'C':[0,0],'A':[500,0]};e=edge('x:0:1','C','A',p)
  # A partial source segment may connect only within the radius too.
  with self.assertRaises(OriginError):attach_origin(g,(0,0),{'m':{}},[segment(e,p)],{},radius=100)
 def test_unknown_gate_behind_origin_need_not_be_crossed(self):
  pts={'B':[100,0],'G':[200,0]};g=graph(pts,[edge('m:0:1','B','G',pts)],'G');p={'A':[0,0],'B':[100,0]}
  e=edge('x:0:1','A','B',p,blocked=True,blocked_nodes=['A'])
  g,s,a=attach_origin(g,(50,0),{'m':{}},[segment(e,p)],{})
  self.assertAlmostEqual(run(g,s)['cost_s'],15)
 def test_bidirectional_origin_can_choose_reverse(self):
  pts={'A':[0,0],'B':[1000,0]};forward=edge('w:0:1','A','B',pts);reverse=edge('w:0:-1','B','A',pts);reverse['direction']=-1
  g=graph(pts,[forward,reverse],'A');g,s,a=attach_origin(g,(250,0),{'w':{}},[],{})
  self.assertAlmostEqual(run(g,s)['cost_s'],25)
 def test_partial_access_cannot_skip_radius(self):
  pts={'M':[500,0],'G':[600,0]};g=graph(pts,[edge('m:0:1','M','G',pts)],'G');p={'O':[-100,0],'M':[500,0]}
  with self.assertRaises(OriginError):attach_origin(g,(0,0),{'m':{}},[segment(edge('x:0:1','O','M',p),p)],{},radius=150)
 def test_gate_permission_precedence(self):
  self.assertTrue(node_allowed('1',{'barrier':'gate','access':'permissive'}))
  self.assertTrue(node_allowed('1',{'barrier':'swing_gate','motor_vehicle':'yes','access':'no'}))
  self.assertFalse(node_allowed('1',{'barrier':'lift_gate'}))
  self.assertFalse(node_allowed('1',{'barrier':'gate','access':'no'}))
  self.assertFalse(node_allowed('1',{'barrier':'gate','access':'private'}))
  self.assertFalse(node_allowed('1',{'barrier':'gate','motorcar':'no','motor_vehicle':'yes'}))
  self.assertFalse(node_allowed('1',{'barrier':'gate','access':'yes','locked':'yes'}))
  self.assertFalse(node_allowed('1',{'barrier':'gate','access':'yes','opening_hours':'08:00-17:00'}))
 def test_restored_strict_gate_link_is_not_width_exception(self):
  pts={'M':[0,0],'A':[20,0],'H':[80,0],'G':[100,0]}
  g=graph(pts,[edge('m:0:1','M','A',pts),edge('z:0:1','H','G',pts)],'G')
  e=edge('gate:0:1','A','H',pts,gate_wait_s=10)
  g,s,a=attach_origin(g,(0,0),{'m':{},'z':{}},[segment(e,pts,width='5')],{})
  result=run(g,s);self.assertAlmostEqual(result['cost_s'],20);self.assertEqual(result['gate_s'],10)
  self.assertEqual(a['restored_strict_edges'],['gate:0:1'])
 def test_explicit_limits_and_private_are_kept(self):
  self.assertEqual(access_policy({'highway':'residential'}),'allowed')
  self.assertEqual(access_policy({'highway':'service'}),'allowed')
  self.assertNotEqual(access_policy({'highway':'residential','width':'2'}),'allowed')
  self.assertNotEqual(access_policy({'highway':'service','access':'private'}),'allowed')
  self.assertNotEqual(access_policy({'highway':'residential','oneway':'reversible'}),'allowed')
  self.assertNotEqual(access_policy({'highway':'service','service':'parking_aisle'}),'allowed')
  self.assertNotEqual(access_policy({'highway':'residential','name':'Gang Melati'}),'allowed')
if __name__=='__main__':unittest.main()
