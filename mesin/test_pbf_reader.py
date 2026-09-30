import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from pbf_reader import blocks, fields, packed, primitives, tags


def vi(n):
    b=bytearray()
    while n>127:
        b.append((n&127)|128); n >>= 7
    b.append(n)
    return bytes(b)


def pb(n,v):
    return vi(n*8+2)+vi(len(v))+v


def fileblock(kind,payload):
    blob=vi(16)+vi(len(payload))+pb(3,zlib.compress(payload))
    header=pb(1,kind)+vi(24)+vi(len(blob))
    return struct.pack('>I',len(header))+header+blob


class PBFTests(unittest.TestCase):
    def test_signed_deltas(self):
        self.assertEqual(list(packed(bytes([20,5,8]),True,True)),[10,7,11])
    def test_tags_and_strings(self):
        raw=pb(1,b''.join(pb(1,x) for x in [b'',b'amenity',b'hospital']))+pb(2,b'')
        strings,g,a,b,groups=primitives(raw)
        self.assertEqual((g,a,b),(100,0,0))
        self.assertEqual(tags([(2,b'\x01'),(3,b'\x02')],strings),{'amenity':'hospital'})
    def test_compressed_roundtrip_and_truncation(self):
        data=fileblock(b'OSMHeader',pb(4,b'OsmSchema-V0.6'))+fileblock(b'OSMData',b'payload')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.pbf'; path.write_bytes(data)
            self.assertEqual([b for b,_ in blocks(path)],[b'payload'])
            path.write_bytes(data[:-2])
            with self.assertRaises(ValueError): list(blocks(path))
    def test_history_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.pbf'; path.write_bytes(fileblock(b'OSMHeader',pb(4,b'HistoricalInformation')))
            with self.assertRaises(ValueError): list(blocks(path))


if __name__=='__main__': unittest.main()
