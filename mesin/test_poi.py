import unittest
from shapely.geometry import LineString,box,Point
from add_poi_penalties import make_zone,covered_length
from ambulance_router import edge_cost

class POITests(unittest.TestCase):
    def test_overlapping_sites_count_once(self):
        zone,parts,tree=make_zone([box(0,0,100,10),box(50,0,150,10)],0)
        self.assertAlmostEqual(covered_length(LineString([(-20,5),(200,5)]),parts,tree),150)
    def test_duplicate_features_invariant(self):
        line=LineString([(-200,0),(200,0)])
        _,p1,t1=make_zone([Point(0,0)],100)
        _,p2,t2=make_zone([Point(0,0),Point(0,0)],100)
        self.assertAlmostEqual(covered_length(line,p1,t1),covered_length(line,p2,t2))
        self.assertAlmostEqual(covered_length(line,p1,t1),200)
    def test_segment_split_invariance(self):
        _,parts,tree=make_zone([box(0,0,100,10),box(50,0,150,10)],0)
        total=covered_length(LineString([(-20,5),(200,5)]),parts,tree)
        split=sum(covered_length(LineString([a,b]),parts,tree) for a,b in [((-20,5),(72,5)),((72,5),(200,5))])
        self.assertAlmostEqual(total,split)
    def test_units_and_four_scenarios(self):
        e={'highway':'primary','length_m':200,'exposure_m':{'school':100,'market':50,'mall':25}}
        for s,expected in [('pagi',36.25),('siang',28.75),('sore',18.75),('malam',5)]:
            c=edge_cost(e,s);self.assertAlmostEqual(c['poi_s'],expected);self.assertAlmostEqual(c['base_s'],18)
    def test_empty_and_outside(self):
        _,parts,tree=make_zone([],100)
        self.assertEqual(covered_length(LineString([(0,0),(100,0)]),parts,tree),0)
        _,parts,tree=make_zone([box(0,0,10,10)],0)
        self.assertEqual(covered_length(LineString([(20,20),(30,30)]),parts,tree),0)

if __name__=='__main__':unittest.main()
