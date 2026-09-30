"""Filter transparan kandidat OSM sesuai cakupan RS umum; bukan verifikasi registrasi."""
import copy
import json
import math
import re
from pathlib import Path

BASE = Path(__file__).parent
SOURCE = BASE/'data_offline/hospital_candidates.geojson'

def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', s.casefold())).strip()


def canonical(s):
    s=norm(s)
    s=re.sub(r'^(rumah sakit(?: umum(?: daerah| pusat)?)?|rsup|rsud|rsu|rsiy|rsi|rspau|rs)\b', '', s).strip()
    # Alias lokal: nama sama dengan PKU dihilangkan, lokasi berdekatan.
    if s == 'muhammadiyah gamping':
        s = 'pku muhammadiyah gamping'
    return s


def classify(p):
    name=norm(p.get('name',''))
    if not name:
        return 'review','Nama kosong'
    if re.search(r'\b(apotek|apotik|klinik|puskesmas|psikologi|psikolog|gym|laboratorium|bekam)\b',name):
        return 'exclude','Fasilitas selain rumah sakit umum'
    if re.search(r'\b(gedung|icu|icc|pusat bedah|stroke center)\b',name):
        return 'exclude','Unit/gedung di dalam RS, bukan tujuan RS tersendiri'
    if re.search(r'\b(khusus|ibu|anak|mata|jiwa|paru|tht|gigi|mulut|bedah|disabilitas|rsia|rskia|rskb|rsk|rsj|rsgm|rskgm)\b',name):
        return 'exclude','Nama menunjukkan RS khusus'
    if not re.search(r'\b(rumah sakit|rs|rsu|rsud|rsup|rsi|rsiy|rspau)\b',name):
        return 'review','Tidak memuat Rumah Sakit atau singkatan yang diizinkan'
    spec={norm(x) for x in p.get('healthcare:speciality','').split(';') if x.strip()}
    if spec and not spec.intersection({'general','umum'}):
        return 'review','Tag spesialisasi perlu pemeriksaan: '+', '.join(sorted(spec))
    if p.get('boundary_review'):
        return 'review','Objek melintasi batas DIY'
    if name=='rsud saedjito':
        return 'review','Kemungkinan salah nama/duplikat RSUP Dr. Sardjito; tidak digabung otomatis'
    return 'include','Lolos filter nama RS dan tidak berindikasi RS khusus'


def distance(a,b):
    x1,y1=a['geometry']['coordinates']; x2,y2=b['geometry']['coordinates']
    p1,p2=map(math.radians,(y1,y2)); dp=p2-p1; dl=math.radians(x2-x1)
    q=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 6371000*2*math.asin(min(1,math.sqrt(q)))


def run():
    features=json.loads(SOURCE.read_text(encoding='utf-8'))['features']
    audit=[]; keep=[]
    # Prefer polygon/area representation, preserving source coordinates and provenance.
    features.sort(key=lambda f:({'relation':0,'way':1,'node':2}[f['properties']['osm_type']],f['properties']['osm_id']))
    for f in features:
        p=f['properties']; decision,reason=classify(p)
        row={'name':p.get('name','(tanpa nama)'), 'osm_url':p['osm_url'],'decision':decision,'reason':reason}
        if decision=='include':
            match=next((g for g in keep if canonical(g['properties']['name'])==canonical(p['name']) and distance(f,g)<=250),None)
            if match:
                row.update(decision='duplicate',reason='Nama setara (termasuk alias PKU Gamping) dan jarak <=250 m',merged_into=match['properties']['osm_url'],distance_m=round(distance(f,match),2))
                match['properties']['source_objects'].append(p['osm_url'])
            else:
                g=copy.deepcopy(f)
                g['properties'].update(selection_status='candidate_general_by_name_not_registry_verified',source_objects=[p['osm_url']],duplicate_review='exact_normalized_name_within_250m_checked')
                keep.append(g)
        audit.append(row)
    keep.sort(key=lambda f:norm(f['properties']['name']))
    target=BASE/'data_offline'
    (target/'hospitals_general_filtered.geojson').write_text(json.dumps({'type':'FeatureCollection','features':keep},ensure_ascii=False,indent=2),encoding='utf-8')
    (target/'hospital_filter_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    count={k:sum(r['decision']==k for r in audit) for k in ['include','exclude','review','duplicate']}
    rows=['# Kandidat RS umum DIY hasil penyaringan','',f"Input: {len(features)} objek. Dipertahankan: {len(keep)} kandidat; dikeluarkan: {count['exclude']}; perlu tinjauan: {count['review']}; duplikat digabung: {count['duplicate']}.",'','Kriteria: kata Rumah Sakit atau padanan RS/RSU/RSUD/RSUP/RSI/RSIY/RSPAU. Nama fasilitas non-RS, unit RS, dan indikasi RS khusus dikeluarkan. Ini filter nama/tag OSM, bukan bukti seluruh kandidat terdaftar sebagai RS umum. Tidak mensyaratkan pintu IGD.','', 'Duplikasi digabung hanya bila nama setelah normalisasi sama dan jarak <=250 meter. Cabang berbeda tidak digabung hanya karena berdekatan. Nama berbeda yang sebenarnya satu RS masih dapat tersisa.','', '| No | Nama OSM | Sumber |','|---:|---|---|']
    for i,f in enumerate(keep,1):
        p=f['properties']; rows.append(f"| {i} | {p['name']} | [OSM]({p['osm_url']}) |")
    rows.extend(['','## Objek yang perlu ditinjau',''])
    rows.extend(f"- {r['name']}: {r['reason']}." for r in audit if r['decision']=='review')
    rows.extend(['','## Duplikat yang digabung',''])
    rows.extend(f"- [{r['name']}]({r['osm_url']}) → [objek utama]({r['merged_into']}); jarak {r['distance_m']} m." for r in audit if r['decision']=='duplicate')
    (BASE/'Daftar_RS_Umum_DIY_Tersaring.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    print(json.dumps(count)); print('Kandidat tujuan:',len(keep))
    assert sum(count.values())==len(features)
    assert all(classify(f['properties'])[0]=='include' for f in keep)
    assert classify({'name':'Apotek Rumah Sakit Contoh'})[0]=='exclude'
    assert classify({'name':'Rumah Sakit Mata Contoh'})[0]=='exclude'
    assert classify({'name':'RSUD Sleman'})[0]=='include'
    assert canonical('RS Universitas Islam Indonesia')==canonical('Rumah Sakit Universitas Islam Indonesia')
    print('Pemeriksaan filter dan jumlah audit lulus.')

if __name__=='__main__': run()
