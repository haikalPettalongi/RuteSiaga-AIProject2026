import unittest
from build_network_offline import road_policy,directions
from route_network import setup,search_network,permitted


class RoadTests(unittest.TestCase):
    def test_directions(self):
        self.assertEqual(directions({'oneway':'-1'}),(-1,))
        self.assertEqual(directions({'junction':'roundabout'}),(1,))
        self.assertEqual(directions({'junction':'roundabout','oneway':'no'}),(1,-1))
        self.assertEqual(directions({'highway':'primary'}),(1,-1))
    def test_access_and_width(self):
        self.assertNotEqual(road_policy({'highway':'primary','access':'private'}),'allowed')
        self.assertNotEqual(road_policy({'highway':'primary','width':'2.8'}),'allowed')
        self.assertNotEqual(road_policy({'highway':'residential'}),'allowed')
        self.assertEqual(road_policy({'highway':'residential','width':'3.5'}),'allowed')
        self.assertNotEqual(road_policy({'highway':'primary','oneway':'reversible'}),'allowed')
        self.assertNotEqual(road_policy({'highway':'footway'}),'allowed')
    def test_turn_requires_detour(self):
        coords={'a':[0,0],'b':[100,0],'c':[200,0],'d':[100,100]}
        def e(i,u,v,w,l=100): return {'id':i,'u':u,'v':v,'way_id':w,'length_m':l,'highway':'primary'}
        data={'nodes':coords,'edges':[e('ab','a','b','1'),e('bc','b','c','2'),e('bd','b','d','3'),e('dc','d','c','4',150)],'turn_restrictions':[{'via':'b','from_way':'1','to_way':'2','restriction':'no_right_turn'}]}
        for a in ['astar','ucs']:
            result=search_network(setup(data),'a',['c'],a)
            self.assertEqual(result['edges'],['ab','bd','dc'])
            self.assertAlmostEqual(result['cost_s'],31.5)
    def test_only_and_uturn(self):
        incoming={'u':'a','v':'b','way_id':'1'}
        straight={'u':'b','v':'c','way_id':'1'};back={'u':'b','v':'a','way_id':'1'}
        rules={('b','1'):[{'from_way':'1','to_way':'1','restriction':'no_u_turn'}]}
        self.assertTrue(permitted(incoming,straight,rules));self.assertFalse(permitted(incoming,back,rules))
        rules={('b','1'):[{'from_way':'1','to_way':'2','restriction':'only_right_turn'}]}
        self.assertFalse(permitted(incoming,straight,rules))
        self.assertTrue(permitted(incoming,{'u':'b','v':'c','way_id':'2'},rules))

if __name__=='__main__': unittest.main()
