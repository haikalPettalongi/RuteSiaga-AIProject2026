# Rekap final — 30 September 2026

Web dan terminal memakai origin_access.py serta route_network.py yang sama. Pencarian nama lokal, pilih titik peta, empat skenario waktu, perbandingan UCS/A*, pemutaran jejak algoritma, dan ekspor JSON tersedia.

Hasil batch: 20 lokasi × 4 skenario = 80 kasus; semua menemukan rute; biaya dan urutan ruas UCS/A* sama pada semua kasus. Ini bukan validasi waktu atau akses lapangan.

Contoh Malioboro Mall → RS Ludira Husada Tama:
| Komponen | Pagi (detik) | Siang (detik) |
|---|---:|---:|
| Dasar | 204,09 | 204,09 |
| Sekolah/pasar/mal | 184,59 | 146,36 |
| Lampu | 175 | 125 |
| Total | 563,68 | 475,45 |

Kedua JSON menggunakan jalur 2.210,93 m dan selisih penanda ke ruas 100,28 m. Google Maps pada screenshot pengguna menampilkan sekitar 8 menit / 2,3 km; waktu keberangkatan dan titik pembanding belum disamakan. Penalti belum diubah untuk menyesuaikan sampel tersebut.

Kode eksperimen, cache aplikasi, dokumen historis, template kosong, dan hasil duplikat dipisahkan ke folder `RuteSiaga_ARSIP_PENDUKUNG` di samping paket final. Data graf yang dipakai mesin tetap berada di dalam paket final.

Pengaturan final: radius penghubung awal default web dan terminal 1 km. Batas pemetaan penanda ke ruas juga 1 km. Hasil JSON dan Excel terdahulu memakai radius penghubung awal 1 km.
