> **Panduan membaca:** teks di dalam <mark>sorotan kuning</mark> adalah bagian yang diubah atau ditambahkan dari draf awal. Sorotan ini untuk pemeriksaan; hapus tag \`<mark>\` dan \`</mark>\` sebelum menyerahkan naskah akhir. Bagian 3 dan 4 tersedia pada berkas laporan terpisah di folder yang sama.

## 1. Introduction

### 1.1 Background

<mark>Pemilihan tujuan ambulans hanya berdasarkan jarak garis lurus berisiko menghasilkan pilihan yang tidak tercepat menurut waktu tempuh.</mark> Aturan satu arah, jalan yang tidak sesuai dengan kriteria model, zona aktivitas seperti sekolah dan pasar, lampu lalu lintas, serta perlintasan kereta sebidang dapat membuat rute yang lebih pendek secara geometris justru mempunyai biaya waktu lebih besar. Di Daerah Istimewa Yogyakarta (DIY), jaringan jalan dari kelas utama hingga jalan lokal membuat pemodelan kendala tersebut relevan.

Data OpenStreetMap (OSM) menyediakan geometri jalan, kelas jalan, arah, atribut akses, dan lokasi objek yang dapat diolah secara komputasional (OpenStreetMap contributors, 2026). Uniform Cost Search (UCS) dan A* dapat digunakan untuk mencari rute berbiaya minimum pada graf. <mark>UCS optimal ketika biaya edge tidak negatif; A* optimal untuk model ini ketika heuristik yang dipakai admissible dan pencarian berhenti saat goal dikeluarkan secara sah dari antrean prioritas.</mark> Dalam proyek ini, biaya yang diminimalkan adalah estimasi waktu perjalanan dalam detik, bukan jarak garis lurus ataupun waktu ambulans yang telah diukur di lapangan.

### 1.2 Problem Statement

Bagaimana membentuk graf jalan berarah berbobot waktu untuk DIY dan menerapkan UCS serta A* guna memilih rute dan rumah sakit dengan estimasi waktu perjalanan minimum dari lokasi asal, sambil mematuhi arah jalan, aturan akses kendaraan, <mark>relasi larangan belok yang didukung sistem</mark>, dan penalti hambatan yang diturunkan dari data OSM? <mark>Tujuan perjalanan pada model ini adalah titik jalan yang menjadi proksi pendekatan ke rumah sakit, bukan pintu IGD yang terverifikasi.</mark>

Pertanyaan evaluasinya adalah: apakah UCS dan A* menghasilkan biaya optimal yang sama untuk input dan graf identik; berapa state yang diperiksa masing-masing; serta bagaimana perbandingan waktu komputasinya pada kasus uji yang sama?

### 1.3 Objective

Tujuan RuteSiaga adalah:

1. membangun graf jalan DIY yang berarah dan berbobot waktu dari data OSM;
2. menerapkan pencarian multitujuan UCS dan A* yang memilih rute serta rumah sakit dalam satu pencarian;
3. menyediakan antarmuka web lokal dengan masukan nama tempat, koordinat, atau pilihan titik pada peta untuk skenario pagi, siang, sore, dan malam; serta
4. membandingkan kesamaan biaya optimal dan efisiensi pencarian kedua algoritma.

Output sistem adalah nama rumah sakit terpilih, geometri dan jarak rute, estimasi waktu, rincian komponen biaya, jumlah state diperiksa, waktu komputasi, berkas JSON, dan animasi penelusuran. <mark>Hasil ini berlaku untuk graf dan parameter model yang digunakan; kelayakan akses fisik menuju rumah sakit serta ketepatan waktu perjalanan nyata belum terverifikasi.</mark>

## 2. Problem Formalization & Algorithm

### 2.1 Problem Formalization

#### 2.1.1 Graph and State Space

Jaringan jalan direpresentasikan sebagai graf berarah berbobot \(G=(V,E)\). \(V\) adalah himpunan node jalan dan \(E\) adalah himpunan ruas berarah. Arah edge dibentuk dari tag OSM, sementara edge yang tidak memenuhi kebijakan akses dan kelayakan model dikeluarkan. Koordinat untuk perhitungan metrik diproyeksikan ke EPSG:32749 (UTM zona 49S), sehingga panjang ruas dinyatakan dalam meter.

<mark>Karena izin belok dapat bergantung pada ruas yang baru dilalui, state pencarian adalah \(s=(v,e_{\mathrm{in}})\), yaitu node \(v\) dan ID ruas masuk \(e_{\mathrm{in}}\). State awal adalah \((v_0,\varnothing)\). Mesin hanya mengembangkan edge keluar yang sesuai arah, akses, dan relasi larangan belok yang didukung. Relasi yang tidak didukung tidak diklaim telah diproses sebagai larangan belok eksplisit; tahap persiapan data menanganinya secara konservatif.</mark>

#### 2.1.2 Input and Output

Input pengguna adalah titik asal berupa nama lokasi, koordinat, atau pilihan titik peta, serta satu skenario waktu. Input sistem mencakup graf jalan, atribut edge, zona pengaruh sekolah/pasar/mal yang telah dihitung sebelumnya, aturan akses dan belok, serta himpunan tujuan \(H\).

<mark>Setiap anggota \(H\) adalah node jalan proksi menuju rumah sakit yang lolos pemetaan model. Sistem aktif memakai 45 node tujuan yang mewakili 44 nama rumah sakit unik; jumlah ini tidak membuktikan kelengkapan semua RS di DIY atau status IGD-nya.</mark> Output adalah rute \(P\), tujuan yang dipilih, biaya waktu minimum menurut model, komponen biaya, dan statistik pencarian. <mark>Jarak lateral dari penanda lokasi ke jalan ditampilkan tetapi tidak masuk dalam biaya perjalanan.</mark>

#### 2.1.3 Edge Cost Function

<mark>Untuk edge \(e\) dan skenario \(t\), fungsi biaya dalam detik adalah
\[
c_t(e)=\frac{L_e}{v_e/3.6}
+\sum_{k\in\{\text{sekolah,pasar,mal}\}}\frac{\ell_{e,k}}{100}p_{k,t}
+I_{\mathrm{lampu}}(e)b_t
+I_{\mathrm{kereta}}(e)r_t
+g_e.
\]
\(L_e\) adalah panjang edge dalam meter; \(v_e\) kecepatan model dalam km/jam; \(\ell_{e,k}\) panjang edge yang terpapar zona jenis \(k\) dalam meter; \(p_{k,t}\) penalti detik per 100 m; \(b_t\) dan \(r_t\) penalti per kejadian; dan \(g_e\) penalti gerbang bila berlaku. Semua suku tidak negatif. Kecepatan model tidak melebihi 60 km/jam.</mark>

<mark>Kecepatan dasar menurut kelas jalan adalah motorway 60, trunk 50, primary 40, secondary 35, tertiary 30, unclassified 25, residential 20, motorway_link 30, trunk_link 30, primary_link 25, secondary_link 25, tertiary_link 20, dan service 10 km/jam. Daftar ini adalah parameter model, bukan kecepatan kendaraan yang diukur. Kelas service digunakan dalam aturan akses awal, bukan diizinkan secara umum pada graf utama.</mark>

<mark>Radius zona sekolah, pasar, dan mal berturut-turut 100 m, 150 m, dan 200 m. Penalti detik per 100 m pada urutan pagi/siang/sore/malam adalah sekolah \(20/15/5/0\), pasar \(30/20/15/5\), dan mal \(5/15/25/10\). Penalti lampu per kejadian adalah \(35/25/40/15\) detik; penalti perlintasan kereta sebidang adalah \(45/30/45/20\) detik. Zona dalam kategori yang sama digabung sebelum paparan dihitung. Contoh: paparan sekolah 50 m pada pagi hari menambah \((50/100)\times20=10\) detik. Ruas jembatan atau terowongan tidak diberi paparan POI oleh tahap persiapan ini; perpotongan jalan dan rel yang terpisah tingkat tidak diberi penalti perlintasan sebidang.</mark>

<mark>Gerbang dengan izin kendaraan yang tercatat dapat mempunyai asumsi tunggu 10 detik; gerbang Grafika yang telah dikonfirmasi dapat dilalui oleh pengguna diasumsikan 0 detik. Status gerbang lain yang tidak jelas tidak otomatis dianggap terbuka. Seluruh penalti adalah asumsi skenario, belum dikalibrasi terhadap waktu tempuh atau waktu tunggu lapangan.</mark>

#### 2.1.4 Goal Test and Objective Function

<mark>Goal test berhasil ketika state \((v,e_{\mathrm{in}})\) dengan \(v\in H\) dikeluarkan secara sah dari priority queue. Berhenti saat suatu goal baru ditemukan belum cukup untuk menjamin biaya minimum. Masalah optimasi adalah
\[
\min_{h\in H}\;\min_{P:v_0\leadsto h}\;\sum_{e\in P}c_t(e),
\]
dengan \(P\) hanya terdiri dari transisi yang sah menurut arah, akses, dan aturan belok. Jika antrean habis, sistem melaporkan tidak ada rute **dalam model** untuk titik asal tersebut; hal ini bukan bukti jalan fisik tidak dapat dilalui.</mark>

### 2.2 Algorithm

Kedua algoritma menggunakan min-heap, kamus biaya terbaik untuk setiap state, dan parent untuk rekonstruksi rute. <mark>UCS memakai prioritas \(f(s)=g(s)\), sedangkan A* memakai \(f(s)=g(s)+h(s)\), dengan \(g(s)\) biaya yang sudah ditempuh. Entri antrean yang usang dilewati dengan membandingkan nilai \(g\) pada entri tersebut dengan biaya terbaik state, bukan membandingkan \(f\) dengan biaya terbaik.</mark>

<mark>Heuristik A* adalah
\[
h(v)=\min_{q\in H}\frac{d_{\mathrm{Euclidean}}(v,q)}{60/3.6},
\]
dalam detik. Karena panjang setiap ruas tidak kurang dari jarak lurus antara ujungnya, kecepatan ruas paling tinggi 60 km/jam, dan penalti tidak negatif, \(h(v)\) tidak melebihi biaya sisa minimum pada graf. Ketaksamaan segitiga juga memberi \(h(u)\leq c_t(u,v)+h(v)\) untuk setiap edge yang sah, sehingga heuristik consistent. Pembatasan belok hanya mengurangi himpunan jalur yang mungkin dan tidak merusak batas bawah tersebut. Jaminan optimalitas berlaku terhadap biaya model, bukan waktu ambulans nyata.</mark>

<mark>Pseudokode implementasi:</mark>

~~~text
siapkan graf dan semua goal untuk skenario t
best[(start, None)] = 0
masukkan state awal ke min-heap
selama heap tidak kosong:
    keluarkan entri dengan prioritas terkecil
    jika g pada entri != best[state]: lanjutkan  # entri usang
    jika node pada state termasuk goal:
        rekonstruksi rute dari parent dan kembalikan hasil
    untuk setiap edge keluar yang sah menurut arah, akses, dan aturan belok:
        next_state = (edge.v, edge.id)
        new_g = g + c_t(edge)
        jika new_g < best.get(next_state, infinity):
            best[next_state] = new_g
            parent[next_state] = (state, edge)
            priority = new_g                  # UCS
            atau priority = new_g + h(edge.v) # A*
            masukkan next_state ke heap
jika heap kosong: laporkan tidak ada rute dalam model
~~~

### 2.3 Design Justification

#### 2.3.1 Choice of Algorithms

UCS dipakai sebagai pembanding karena biaya edge tidak negatif dan UCS mencari rute berbiaya minimum tanpa heuristik. <mark>Biaya UCS menjadi **acuan optimal pada graf dan fungsi biaya model**, bukan ground truth waktu perjalanan di lapangan.</mark> A* digunakan untuk melihat apakah batas bawah geometris dapat mengurangi jumlah state yang diperiksa tanpa mengubah biaya optimum. <mark>Pengurangan jumlah state bukan jaminan A* selalu lebih cepat: heuristik dihitung terhadap banyak titik tujuan. Hasil batch proyek ini menunjukkan A* memeriksa lebih sedikit state pada 80 dari 80 kasus, tetapi rata-rata waktu pencariannya lebih tinggi daripada UCS; rincian terdapat pada Bagian 4.3.</mark>

#### 2.3.2 Choice of Heuristic

Jarak Euclidean dalam UTM dibagi kecepatan maksimum model dipilih karena satuannya detik, mudah dihitung, dan merupakan batas bawah biaya waktu pada graf. Penghitungan langsung minimum jarak ke seluruh tujuan memerlukan \(O(|H|)\) pekerjaan per node yang belum tersimpan dalam cache. Heuristik ini tidak mengukur kemacetan; fungsinya hanya mengarahkan pencarian tanpa melebihkan biaya sisa.

#### 2.3.3 Choice of Data

OSM dipilih karena menyediakan atribut jalan, arah, akses, POI, dan infrastruktur yang relevan bagi model. Snapshot Geofabrik 20 September 2026 memungkinkan eksperimen pada data tetap. <mark>Graf turunan sudah tersedia dalam paket aplikasi; untuk **membangun ulang ekstraksi dari awal**, pengguna tetap memerlukan PBF sumber yang tidak disertakan dalam folder final.</mark>

#### 2.3.4 Cost Parameters

Penalti POI, lampu, perlintasan kereta, gerbang, dan kecepatan dasar adalah asumsi eksperimen untuk membedakan skenario secara kuantitatif. Pola seperti penalti sekolah lebih besar pada pagi hari dan penalti mal lebih besar pada sore hari didasarkan pada hipotesis aktivitas kawasan. Besarnya belum dikalibrasi menggunakan pengamatan lapangan.

#### 2.3.5 Model Limitations

<mark>Kelas jalan OSM merupakan proksi kelayakan ambulans, bukan bukti lebar fisik atau kondisi permukaan seluruh ruas. Titik asal ditempatkan pada ruas jalan terdekat dalam radius pemetaan 1 km; jarak dari penanda ke ruas dan akses fisiknya belum masuk biaya. Tujuan adalah proksi titik jalan rumah sakit, bukan pintu IGD. Daftar rumah sakit belum terbukti lengkap, sedangkan status layanan IGD dan keterbukaan semua gerbang tidak diverifikasi. Biaya skenario dibekukan selama pencarian dan tidak mengikuti perubahan lalu lintas secara langsung. Karena itu, hasil adalah optimum pada graf dan parameter penelitian, bukan rekomendasi operasional ambulans yang sudah tervalidasi.</mark>

### References

Russell, S. J., & Norvig, P. (2010). *Artificial Intelligence: A Modern Approach* (3rd ed.). Prentice Hall. https://aima.cs.berkeley.edu/3rd-ed/

Geofabrik GmbH. (2026). *OpenStreetMap data extracts — Java*. https://download.geofabrik.de/asia/indonesia/java.html (snapshot yang digunakan: 20 September 2026).

<mark>OpenStreetMap contributors. (2026). *OpenStreetMap* [basis data], berlisensi ODbL. https://www.openstreetmap.org/copyright</mark>
