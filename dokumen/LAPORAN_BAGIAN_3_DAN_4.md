## 3. Data & System Design

### 3.1 Data / Knowledge Source

RuteSiaga menggunakan cuplikan data OpenStreetMap (OSM) wilayah Jawa dari Geofabrik, yaitu berkas java-260920.osm.pbf bertanggal 20 September 2026. Berkas sumber tersebut berukuran 896.987.462 byte. Pemrosesan dilakukan secara lokal sehingga hasil eksperimen tidak berubah karena pembaruan peta daring saat aplikasi dijalankan. Cakupan model adalah Daerah Istimewa Yogyakarta (DIY) dengan buffer 10 km di luar batas wilayah, agar ruas yang melintasi perbatasan tidak langsung terpotong. Berkas PBF mentah tidak disertakan dalam paket aplikasi karena ukurannya besar; data turunan yang diperlukan untuk menjalankan aplikasi sudah disertakan.

Data yang digunakan meliputi geometri dan kelas jalan (tag highway), arah dan pembatasan akses kendaraan, atribut lebar atau pembatas dimensi bila tersedia, relasi larangan belok, lampu lalu lintas, perlintasan kereta sebidang, lokasi sekolah, pasar dan mal, serta objek rumah sakit. Seluruh geometri untuk penghitungan panjang dan jarak diproyeksikan ke EPSG:32749 (UTM zona 49S), sehingga satuannya meter. OSM dipilih karena atribut-atribut tersebut dapat membentuk graf jalan berarah dan biaya perjalanan, tetapi kelengkapan serta kebenaran atribut di lapangan belum dijamin.

Hasil ekstraksi graf dasar memuat 169.944 node dan 330.774 ruas berarah. Dari 138 objek rumah sakit kandidat dalam DIY, penyaringan nama dan jenis fasilitas menghasilkan 50 kandidat rumah sakit umum. Sebanyak 44 kandidat mempunyai proksi titik jalan pada komponen jaringan terbesar dengan syarat pemetaan yang ditetapkan; enam kandidat lain perlu pemeriksaan. Sistem aktif menambahkan satu titik pendekatan jalan untuk RSUP Dr. Sardjito berdasarkan audit data OSM. Dengan demikian tersedia 45 titik tujuan jalan yang mewakili 44 nama rumah sakit unik, bukan 45 rumah sakit berbeda. Titik tujuan adalah proksi di jaringan jalan menuju rumah sakit, bukan pintu IGD atau bukti bahwa seluruh rumah sakit DIY sudah tercakup.

Untuk penalti lokasi, data turunan mencatat 1.871 objek sekolah, 376 pasar dan 20 mal. Angka ini adalah jumlah objek yang berhasil diekstrak dari snapshot OSM, bukan sensus fasilitas di DIY. Radius pengaruh yang digunakan berturut-turut 100 m, 150 m dan 200 m. Sumber dan angka ekstraksi dapat diperiksa pada data_offline/inventory_report.json, network_diy/network_report.json dan network_diy/poi/penalty_report.json di folder mesin.

### 3.2 Data Preparation

Persiapan data berlangsung dalam empat tahap. Pertama, objek OSM dibaca dari PBF lokal dan dibatasi pada DIY beserta buffer 10 km. Kedua, jalan diseleksi memakai kelas highway serta atribut akses, lebar, permukaan, dimensi kendaraan dan arah. Kelas utama seperti motorway, trunk, primary, secondary dan tertiary, termasuk penghubungnya, dapat masuk graf jika lolos aturan. Jalan residential dan unclassified hanya masuk graf utama bila lebar eksplisitnya memenuhi ambang asumsi 3 m. Jalan service tidak otomatis masuk graf utama; akses awal dari lokasi keberangkatan ditangani secara terpisah. Jalan pejalan kaki, jalur sepeda, gang yang terwakili oleh kelas atau lebar yang tidak memenuhi syarat, serta ruas dengan larangan akses yang diketahui dikeluarkan. Ambang dan kelas jalan adalah proksi kelayakan, bukan hasil pengukuran lebar seluruh ruas.

Ketiga, ruas yang lolos diubah menjadi edge berarah. Tag satu arah dipertahankan, sedangkan jalan dua arah dibuat menjadi dua edge. Relasi larangan belok yang didukung dimasukkan sebagai aturan perpindahan dari ruas masuk ke ruas keluar. Panjang ruas dihitung dalam meter pada EPSG:32749. Atribut lokasi kemudian diproyeksikan ke ruas: panjang paparan sekolah, pasar dan mal dihitung dari irisan geometri ruas dengan zona pengaruh. Zona yang bertumpang tindih dalam kategori yang sama digabung agar panjang paparan tidak dihitung berulang. Ruas yang ditandai sebagai jembatan atau terowongan tidak diberi paparan POI oleh tahap ini; perlintasan kereta sebidang hanya dikenai penalti jika data menandainya sebagai perlintasan pada jalan yang tidak dipisahkan tingkat. Aturan ini masih bergantung pada ketepatan tag OSM.

Keempat, objek rumah sakit disaring dan dipetakan ke node jalan yang memenuhi kriteria model. Sistem tidak membuat sambungan lurus fiktif dari node jalan ke pintu rumah sakit. Pada saat pengguna memilih titik asal, sistem mencari ruas terdekat dalam katalog akses dan membuat titik awal pada ruas itu dengan memperhatikan arah perjalanan. Jarak pencarian penghubung awal dibatasi 1 km. Ruas lokal atau service yang memenuhi aturan akses dapat digunakan hanya pada tahap penghubung awal; setelah mencapai jaringan utama yang terhubung ke tujuan, rute mengikuti aturan graf utama. Jarak lateral dari penanda lokasi ke ruas ditampilkan, tetapi tidak dimasukkan ke estimasi waktu. Pemilihan ruas terdekat belum membuktikan akses fisik dari bangunan atau halaman ke ruas tersebut.

Biaya ruas dihitung dalam detik sebagai jumlah waktu dasar, penalti paparan POI, penalti lampu, penalti perlintasan kereta dan, jika berlaku, penalti gerbang. Waktu dasar adalah panjang ruas dibagi kecepatan model per kelas jalan. Semua komponen dijaga tidak negatif. Parameter skenario pagi, siang, sore dan malam merupakan asumsi penelitian yang dibekukan selama satu pencarian, bukan data kemacetan langsung. Data turunan yang diperlukan aplikasi tersimpan sebagai graph_diy_poi.json, access_catalog.sqlite, indeks lokasi dan berkas aturan pendukung di dalam folder final.

### 3.3 System Architecture

Alur sistem adalah: pengguna memasukkan nama tempat, koordinat atau memilih titik pada peta; antarmuka memperoleh koordinat; modul akses awal memproyeksikan titik ke ruas jalan; mesin membentuk graf pencarian sesuai skenario waktu; UCS dan A* mencari rumah sakit tujuan dari himpunan tujuan yang sama; server membandingkan biaya keduanya; antarmuka menampilkan rute, nama rumah sakit, estimasi waktu, rincian biaya dan statistik pencarian. Nama tempat dicari pada indeks lokal OSM. Jika suatu tempat tidak ada di indeks, pengguna dapat memasukkan koordinat atau memilih titik peta.

Komponen utama terdiri atas (1) data graf dan katalog akses; (2) modul origin_access.py untuk pemetaan titik asal; (3) ambulance_router.py untuk parameter biaya; (4) route_network.py untuk UCS, A* dan larangan belok; (5) web/server.py sebagai penghubung mesin dengan antarmuka; serta (6) halaman web HTML, CSS dan JavaScript. Terminal dan web memakai modul inti pencarian yang sama. Server menghentikan permintaan jika biaya optimal UCS dan A* tidak cocok, sehingga perbedaan hasil tidak diam-diam ditampilkan sebagai rute sah. Animasi penelusuran pada web adalah visualisasi state yang diperiksa, bukan proses navigasi ambulans secara langsung.

Peta di halaman web digambar dari segmen OSM lokal yang disederhanakan untuk tampilan. Pada cakupan pandang luas, peta hanya menampilkan kelas jalan utama agar tetap responsif. Penyederhanaan tampilan tersebut tidak mengubah graf yang dipakai mesin untuk menghitung rute.

### 3.4 Technology

Implementasi memakai Python 3.14. Pencarian prioritas menggunakan heapq dari pustaka standar; server lokal memakai http.server. NumPy dan Shapely membantu proyeksi titik ke ruas serta operasi geometri, sedangkan NetworkX digunakan dalam persiapan atau validasi jaringan. Katalog akses disimpan dalam SQLite. Antarmuka satu halaman memakai HTML, CSS, JavaScript dan gambar vektor SVG tanpa layanan peta daring. Aplikasi berjalan di komputer lokal pada http://127.0.0.1:8765/. Berkas requirements.txt mencatat paket Python yang diperlukan. Berkas sumber OSM mentah diperlukan untuk mengulang ekstraksi dari awal, tetapi tidak diperlukan untuk menjalankan graf turunan yang sudah tersedia.

## 4. Implementation & Results

### 4.1 Algorithm Implementation

State pencarian didefinisikan sebagai pasangan (node saat ini, ID ruas masuk). Definisi ini diperlukan karena izin belok bergantung pada ruas sebelumnya. UCS dan A* memakai struktur pencarian yang sama: min-heap, catatan biaya terbaik untuk setiap state, serta parent untuk merekonstruksi jalur. UCS mengurutkan antrean menurut biaya yang sudah ditempuh, g(s). A* memakai g(s) + h(s), dengan h(s) berupa jarak lurus dari node saat ini ke titik tujuan terdekat dibagi kecepatan maksimum model 60 km/jam atau sekitar 16,67 m/s. Penalti dan panjang ruas tidak negatif, sehingga heuristik tersebut merupakan batas bawah biaya waktu model. Pencarian berhenti ketika suatu titik tujuan dikeluarkan secara sah dari antrean, bukan saat pertama kali terlihat.

Alur utama implementasi adalah sebagai berikut:

~~~text
siapkan graf dan semua node tujuan RS sesuai skenario
masukkan state awal dengan g = 0 ke min-heap
selama heap tidak kosong:
    keluarkan state dengan prioritas terkecil
    abaikan entri lama jika g bukan biaya terbaik state itu
    jika node state termasuk tujuan: bangun ulang dan kembalikan rute
    untuk tiap edge keluar yang sah menurut arah, akses, dan aturan belok:
        hitung g_baru = g + biaya edge dalam detik
        bila g_baru memperbaiki biaya state berikutnya:
            simpan parent dan g_baru
            masukkan dengan prioritas g_baru (UCS)
            atau g_baru + h(node berikutnya) (A*)
jika heap habis: laporkan tidak ada rute dalam model
~~~

Satu pencarian memuat seluruh tujuan RS sekaligus. Karena itu, hasilnya adalah tujuan dengan biaya waktu minimum pada graf yang tersedia; sistem tidak perlu menjalankan pencarian terpisah untuk setiap RS. Contoh Jalan Grafika memperlihatkan proses tersebut: titik asal dipetakan ke Jalan Grafika dengan selisih 7,08 m, lalu kedua algoritma mencapai proksi jalan RSUP Dr. Sardjito dengan biaya 44,89 detik dan panjang rute 249,41 m dalam skenario pagi. Nilai tersebut adalah biaya model menuju titik jalan, bukan waktu sampai pintu IGD.

### 4.2 System Implementation

Pengguna dapat mencari nama lokasi dari indeks lokal OSM, memasukkan lintang dan bujur, atau memilih titik pada peta. Setelah skenario waktu dipilih, permintaan dikirim ke server lokal. Server menjalankan pemetaan akses awal, membangun biaya ruas untuk skenario tersebut, lalu menjalankan UCS dan A*. Respons memuat titik jalan awal, selisih lokasi-ke-jalan, nama rumah sakit terpilih, jarak rute, total detik, rincian waktu dasar/POI/lampu/kereta/gerbang, jumlah state yang diperiksa, waktu komputasi serta geometri rute. Hasil dapat diunduh sebagai JSON.

Jika titik asal tidak dapat dipetakan atau tidak ada rute menurut batasan graf, sistem memberikan pesan gagal alih-alih mengarang sambungan jalan. Peta antarmuka menampilkan lokasi awal, titik RS, rute serta animasi jejak pemeriksaan state. Waktu komputasi algoritma pada hasil uji di bawah hanya mengukur pencarian; pemuatan data, persiapan akses dan penggambaran web tidak termasuk angka tersebut.

### 4.3 Results

Pengujian utama menggunakan 20 lokasi asal dan empat skenario waktu, sehingga menghasilkan 80 kasus. Tiga lokasi berasal dari koordinat yang diberikan pengguna. Untuk 17 lokasi lain, skrip uji memilih titik jalan OSM secara otomatis di dekat penanda tempat; akses fisik dari penanda ke jalan belum diverifikasi. Semua 80 kasus menemukan rute. Biaya optimal UCS dan A* sama dalam batas toleransi 10^-6 detik, dan urutan edge rute akhirnya juga sama pada semua kasus.

| Metrik pada 80 kasus | UCS | A* |
|---|---:|---:|
| Jumlah state diperiksa, seluruh kasus | 264.494 | 153.311 |
| Rata-rata state diperiksa per kasus | 3.306,18 | 1.916,39 |
| Rata-rata waktu pencarian per kasus | 32,82 ms | 36,80 ms |
| Kasus dengan waktu pencarian lebih cepat | 66 | 14 |

A* memeriksa lebih sedikit state pada setiap kasus, dengan pengurangan total sekitar 42,04% dibanding UCS. Namun, pada pengukuran batch ini A* tidak lebih cepat dalam waktu komputasi rata-rata. Perhitungan heuristik ke banyak tujuan menambah pekerjaan per state. Waktu dalam milidetik dipengaruhi perangkat, cache dan kondisi saat program dijalankan, sehingga tabel ini adalah hasil satu batch pengukuran, bukan jaminan performa umum. Kesamaan biaya dan jalur menunjukkan konsistensi kedua implementasi pada kasus uji, bukan validasi bahwa estimasi waktu sesuai perjalanan ambulans nyata.

Rata-rata biaya rute model untuk 20 lokasi yang sama adalah 592,55 detik pada pagi, 529,67 detik pada siang, 510,60 detik pada sore, dan 404,10 detik pada malam. Perbedaan ini berasal dari parameter penalti skenario yang ditetapkan dalam model; angka tersebut tidak boleh dibaca sebagai bukti empiris bahwa seluruh perjalanan malam di DIY selalu lebih cepat. Beberapa lokasi mungkin memilih tujuan atau rute berbeda antarskenario.

| Contoh kasus dari hasil batch | RS terpilih | Panjang rute | Biaya UCS = A* | State UCS / A* |
|---|---|---:|---:|---:|
| Jalan Grafika, pagi | RSUP Dr. Sardjito | 249,41 m | 44,89 detik | 43 / 36 |
| Jalan Tentara Pelajar, pagi | Rumah Sakit Dr Soetarto | 2,75 km | 547,82 detik | 922 / 847 |
| Malioboro Mall, pagi | Rumah Sakit Ludira Husada Tama | 2,21 km | 563,58 detik | 346 / 305 |

Pada baris Malioboro Mall, skrip batch terlebih dahulu memindahkan titik penanda OSM ke ruas jalan terdekat sekitar 100,28 m dari penanda. Biaya 563,58 detik tidak menghitung perpindahan lateral tersebut. Input langsung pada penanda dapat menghasilkan angka sedikit berbeda.

Validasi tambahan pada graf dasar membandingkan pencarian dengan oracle NetworkX berbasis Dijkstra untuk 56 pasangan kueri dan 112 kali pencarian UCS/A*. Laporan validasi mencatat delapan kueri tak terjangkau dan hasil biaya yang cocok untuk kueri yang terjangkau. Pengujian ini mendukung ketepatan implementasi pencarian terhadap graf dan biaya yang sama, tetapi belum menguji kebenaran kondisi jalan, gerbang, kemacetan maupun waktu tempuh lapangan. Berkas bukti utama adalah hasil/json_otomatis/hasil_batch.json, hasil/excel/Hasil_Uji_RuteSiaga_20_Lokasi.xlsx dan mesin/network_diy/validation_poi_report.json.

### 4.4 Working System

Contoh penggunaan: jalankan Jalankan-Web.cmd, buka http://127.0.0.1:8765/, masukkan koordinat Jalan Grafika (-7,766067024356544; 110,37390636072011), pilih skenario pagi, lalu tekan tombol pencarian. Sistem menampilkan RSUP Dr. Sardjito sebagai tujuan tercepat menurut biaya model, rute pada peta, estimasi 44,89 detik, dan perbandingan 43 state UCS dengan 36 state A*. Pengguna dapat memutar animasi penelusuran atau mengunduh rincian JSON.

Untuk memenuhi syarat screenshot pada struktur laporan, sisipkan tangkapan layar aplikasi setelah rute contoh benar-benar tampil di komputer. Gunakan keterangan: **Gambar 4.1. Tampilan RuteSiaga untuk titik awal Jalan Grafika pada skenario pagi; rute dan waktu adalah estimasi model menuju titik jalan rumah sakit.** Tangkapan layar belum disertakan di berkas ini agar laporan tidak menyajikan gambar yang belum diverifikasi dari aplikasi berjalan.

### Sumber untuk Bab 3–4

- Geofabrik GmbH. (2026). *OpenStreetMap data extracts — Java*. https://download.geofabrik.de/asia/indonesia/java.html (snapshot lokal java-260920.osm.pbf, 20 September 2026).
- OpenStreetMap contributors. (2026). *OpenStreetMap* [basis data], berlisensi ODbL. https://www.openstreetmap.org/copyright
- RuteSiaga_FINAL/mesin/network_diy/network_report.json; RuteSiaga_FINAL/mesin/network_diy/poi/penalty_report.json; RuteSiaga_FINAL/hasil/json_otomatis/hasil_batch.json; RuteSiaga_FINAL/mesin/network_diy/validation_poi_report.json (data dan hasil proyek, diakses 30 September 2026).
