"""Pembaca streaming OSM PBF raw/zlib, berdasarkan schema OSM-binary.
https://github.com/openstreetmap/OSM-binary/tree/master/osmpbf
Tidak mengubah berkas sumber; menolak fitur history dan kompresi tak didukung.
"""
import struct
import zlib


def varint(data, pos):
    value = 0
    for shift in range(0, 70, 7):
        byte = data[pos]
        pos += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, pos
    raise ValueError('Varint invalid')


def fields(data):
    pos = 0
    while pos < len(data):
        key, pos = varint(data, pos)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, pos = varint(data, pos)
        elif wire == 2:
            size, pos = varint(data, pos)
            value = data[pos:pos + size]
            if len(value) != size:
                raise ValueError('PBF terpotong')
            pos += size
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            value = data[pos:pos + size]
            pos += size
        else:
            raise ValueError(f'Wire type unsupported: {wire}')
        yield number, value


def packed(data, signed=False, delta=False):
    pos, acc = 0, 0
    while pos < len(data):
        value, pos = varint(data, pos)
        if signed:
            value = (value >> 1) ^ -(value & 1)
        if delta:
            acc += value
            yield acc
        else:
            yield value


def unpack_field(items, key, signed=False, delta=False):
    # Multiple packed chunks are legal: concatenate before delta decoding.
    return packed(b''.join(v for k, v in items if k == key), signed, delta)


def blocks(path):
    with open(path, 'rb') as f:
        first = True
        while True:
            size_bytes = f.read(4)
            if not size_bytes:
                break
            if len(size_bytes) != 4:
                raise ValueError('Header berkas terpotong')
            size = struct.unpack('>I', size_bytes)[0]
            if not 0 < size < 65536:
                raise ValueError('Ukuran header invalid')
            header = dict(fields(f.read(size)))
            blob_size = header[3]
            if not 0 < blob_size <= 32 * 1024 * 1024:
                raise ValueError('Ukuran blob invalid')
            blob_bytes = f.read(blob_size)
            if len(blob_bytes) != blob_size:
                raise ValueError('Unduhan belum lengkap: blob terpotong')
            blob = dict(fields(blob_bytes))
            if 1 in blob:
                raw = blob[1]
            elif 3 in blob:
                raw = zlib.decompress(blob[3])
            else:
                raise ValueError('Kompresi PBF belum didukung')
            if 2 in blob and blob[2] != len(raw):
                raise ValueError('Panjang data hasil dekompresi tidak cocok')
            kind = header[1]
            if first and kind != b'OSMHeader':
                raise ValueError('Bukan berkas OSM PBF standar')
            first = False
            if kind == b'OSMHeader':
                required = [v for k, v in fields(raw) if k == 4]
                if set(required) - {b'OsmSchema-V0.6', b'DenseNodes'}:
                    raise ValueError(f'Fitur wajib tidak didukung: {required}')
            elif kind == b'OSMData':
                yield raw, f.tell()
        if first:
            raise ValueError('Berkas kosong')


def primitives(raw):
    items = list(fields(raw))
    table = next(v for k, v in items if k == 1)
    strings = [v.decode('utf-8') for k, v in fields(table) if k == 1]
    scalar = {k: v for k, v in items if k in (17, 19, 20)}
    granularity = scalar.get(17, 100)
    def int64(x):
        return x - (1 << 64) if x >= (1 << 63) else x
    lat_offset = int64(scalar.get(19, 0))
    lon_offset = int64(scalar.get(20, 0))
    return strings, granularity, lat_offset, lon_offset, [v for k, v in items if k == 2]


def tags(items, strings):
    return {strings[k]: strings[v] for k, v in zip(unpack_field(items, 2), unpack_field(items, 3), strict=True)}
