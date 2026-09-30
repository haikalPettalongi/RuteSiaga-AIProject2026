import unittest
from pathlib import Path
import server
from location_search import search,normalize
class LocationSearchTests(unittest.TestCase):
 def test_expanded_places_and_aliases(self):
  for query,name in [('UGM','Universitas Gadjah Mada'),('Malioboro Mall','Malioboro Mall'),('Kost Putra Hikmah','Kos Putra "Hikmah"'),('Wisma Bahasa','Wisma Bahasa')]:
   r=search(server.ENGINE,server.ROOT/'locations_index.json',query)
   self.assertEqual(r['results'][0]['name'],name)
  self.assertEqual(search(server.ENGINE,server.ROOT/'locations_index.json','Kos Putra Wisma Abiyoso')['total'],0)
 def test_name_and_abbreviation(self):
  self.assertEqual(normalize('Jl. Tentara Pelajar'),normalize('Jalan Tentara Pelajar'))
  r=search(server.ENGINE,server.ROOT/'locations_index.json','Jalan Grafika')
  self.assertTrue(r['results'])
  self.assertEqual(r['results'][0]['name'],'Jalan Grafika')
 def test_unknown_and_short_query(self):
  self.assertEqual(search(server.ENGINE,server.ROOT/'locations_index.json','zzzznotfound')['total'],0)
  with self.assertRaises(ValueError):search(server.ENGINE,server.ROOT/'locations_index.json','a')
if __name__=='__main__':unittest.main()
