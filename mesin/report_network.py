"""Ringkasan manusia dan peta statis hasil jaringan."""
import json
from pathlib import Path
import os
cache=Path(__file__).resolve().parent.parent/'work'/'matplotlib'
cache.mkdir(parents=True,exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR',str(cache))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from pyproj import Transformer

BASE=Path(__file__).parent;NET=BASE/'network_diy'
r=json.loads((NET/'network_report.json').read_text()); v=json.loads((NET/'validation_report.json').read_text());m=json.loads((NET/'hospital_road_mapping.json').read_text(encoding='utf-8'));g=json.loads((NET/'graph_diy.json').read_text(encoding='utf-8'))
lines=['# Hasil pembentukan jaringan jalan DIY','',f"Graf: **{r['nodes']:,} node**, **{r['directed_edges']:,} ruas berarah**, dari **{r['ways']:,} OSM ways**.",'',f"Dari {r['hospital_candidates']} kandidat RS, **{r['hospital_road_proxies']}** mendapat titik jalan proksi dan **{r['hospitals_need_review']}** perlu pemeriksaan. Ada {r['unique_goal_nodes']} node tujuan unik.",'','## Apa yang telah diuji','',f"- 15 tes otomatis lulus, termasuk graf acak dengan larangan belok.",f"- {v['query_pairs']} kueri berpasangan ({v['search_runs']} pencarian) pada empat skenario cocok dengan pembanding NetworkX pada graf state ruas masuk.",'- Semua ruas memiliki panjang positif, endpoint yang tersedia, kelas/akses yang lolos kebijakan, dan arah yang sesuai tag OSM.',f"- {r['turn_rules']} aturan belok dimodelkan. Untuk relasi yang belum didukung, {r['unsupported_restriction_from_ways_excluded']} from-way dikeluarkan secara konservatif.",'','## Batas validitas','', '- Ini validasi perhitungan pada graf, bukan bukti lebar, kondisi jalan, akses RS, atau waktu ambulans di lapangan.', '- Titik tujuan adalah node jalan terdekat dengan jarak maksimal 150 m, berada di komponen lemah terbesar dan mempunyai ruas masuk. Tidak dibuat sambungan lurus yang dianggap jalan kendaraan. Titik tersebut belum menjamin akses fisik ke RS; salah sisi jalan, tembok atau sungai masih perlu pemeriksaan.', '- Nilai waktu hanya mencakup waktu dasar dan asumsi penalti node lampu/palang. Paparan sekolah/pasar/mal belum dihitung pada tahap jaringan ini. Belum ada klaim waktu tempuh aktual.', '- Lampu dan perlintasan masih mengikuti node OSM; pengelompokan beberapa node menjadi satu kejadian fisik belum selesai.', '- Jalan utama diterima berdasarkan proksi kelas; jalan residential/unclassified hanya diterima jika width numerik >=3 m. Service belum dimasukkan tanpa audit akses. Kebijakan konservatif dapat memutus rute yang sebenarnya ada.', '- Batas DIY dari cache Nominatim relation 5616105 diberi buffer 10 km. Belum diuji terhadap buffer lebih luas; optimalitas hanya berlaku pada graf ini.', '- Daftar 50 kandidat RS berasal dari penyaringan OSM; belum merupakan daftar resmi lengkap RS umum.', '- Relasi belok node-via standar dipatuhi oleh route_network.py. Pembatas yang belum didukung menghapus from-way, sehingga pilihan rute dapat lebih terbatas daripada kondisi nyata.','', '## Pemetaan RS','', '| RS | Jarak ke titik jalan (m) | Status | ID node jalan |','|---|---:|---|---|']
for h in sorted(m,key=lambda x:x['name'].casefold()):
    status='Proksi jalan; akses belum diverifikasi' if h['status']=='road_point_proxy' else 'Perlu pemeriksaan; tidak menjadi goal'
    lines.append(f"| {h['name']} | {h['gap_m']:.2f} | {status} | {h['road_node']} |")
lines+=['','## Cara menjalankan ulang','', 'Dari folder outputs:', '', '```powershell', '& "..\\work\\.venv\\Scripts\\python.exe" build_network_offline.py --reuse', '& "..\\work\\.venv\\Scripts\\python.exe" validate_network.py', '```', '', 'Untuk pencarian gunakan route_network.py, bukan ambulance_router.py, karena graf nyata mempunyai larangan belok.', '', '## Sumber aturan', '', '- https://wiki.openstreetmap.org/wiki/Key:oneway', '- https://wiki.openstreetmap.org/wiki/Relation:restriction', '- https://wiki.openstreetmap.org/wiki/Key:access', '- Data peta: OpenStreetMap contributors, melalui Geofabrik java-260920.osm.pbf (ODbL).']
(BASE/'Hasil_Jaringan_Jalan_DIY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
segments=[];seen=set()
for e in g['edges']:
    key=(e['way_id'],e['segment_index'])
    if key in seen:continue
    seen.add(key);segments.append([[a/1000 for a in g['nodes'][e['u']]],[a/1000 for a in g['nodes'][e['v']]]])
fig,ax=plt.subplots(figsize=(10,9),dpi=160)
ax.add_collection(LineCollection(segments,colors='#8296a4',linewidths=.35,rasterized=True))
project=Transformer.from_crs(4326,32749,always_xy=True)
for status,color,label in [('road_point_proxy','#007e87','Lokasi RS dengan proksi jalan'),('requires_review','#c75d26','RS perlu pemeriksaan sambungan')]:
    pts=[project.transform(*h['hospital_lonlat']) for h in m if h['status']==status]
    if pts:ax.scatter([p[0]/1000 for p in pts],[p[1]/1000 for p in pts],s=24,c=color,label=label,zorder=3,edgecolors='white',linewidths=.5)
ax.autoscale();ax.set_aspect('equal');ax.set_title('Jaringan jalan DIY dan kandidat rumah sakit\nGraf konservatif untuk penelitian; akses RS belum diverifikasi',loc='left',fontsize=13)
ax.set_xlabel('Easting UTM 49S (km)');ax.set_ylabel('Northing UTM 49S (km)');ax.legend(loc='lower left',fontsize=8);ax.grid(alpha=.15)
fig.text(.12,.025,'Sumber: OpenStreetMap contributors / Geofabrik 20-09-2026. Jalan mencakup buffer luar DIY.',fontsize=8)
fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(BASE/'Peta_Jaringan_RS_DIY.png');plt.close(fig)
print('Laporan dan peta selesai.')
