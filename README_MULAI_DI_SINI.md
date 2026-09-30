# RuteSiaga — paket final

## Menjalankan
### Versi Streamlit (untuk tautan publik)
1. Di komputer ini, klik dua kali **Jalankan-Streamlit.cmd**. Bila dependensi belum ada, jalankan **Siapkan-Python.cmd** dahulu.
2. Untuk menayangkan di Streamlit Community Cloud, buat repositori GitHub dan unggah **seluruh isi folder final ini**, termasuk berkas graf Git LFS (`git lfs push --all origin main`). Jangan unggah folder `RuteSiaga_RUNTIME_LOKAL`.
3. Di [share.streamlit.io](https://share.streamlit.io), pilih **Create app**, repositori tersebut, branch `main`, dan entrypoint `streamlit_app.py`; pilih Python 3.14 bila tersedia. Alamat publik baru ada setelah deploy berhasil.
4. Verifikasi di alamat publik: cari tempat, klik peta, dan hitung contoh `-7.79334345, 110.3666525377634` skenario pagi. Hasil yang diharapkan: Rumah Sakit Ludira Husada Tama, sekitar 563,68 detik untuk UCS dan A*.

Paket data besar (SQLite sekitar 1,3 GB dan graf JSON sekitar 159 MB) dapat membuat proses membangun/menjalankan aplikasi di layanan gratis lambat atau kehabisan memori. Status deploy publik **belum diverifikasi** karena repositori GitHub belum tersedia. Peta dasar OpenStreetMap dan Streamlit memerlukan internet, sedangkan perhitungan rute memakai data paket.
Pencarian nama menggunakan indeks OSM dalam paket, jadi nama yang tidak ada di indeks mungkin tidak ditemukan. Pilih titik di peta atau masukkan koordinat untuk kasus itu. Kebijakan Windows Application Control pada komputer ini juga dapat memblokir DLL Python; ini masalah lingkungan lokal, bukan hasil uji hosting Streamlit.

### Versi web lokal
1. Tutup server RuteSiaga lama (Ctrl+C pada terminalnya) agar port 8765 bebas.
2. Klik dua kali **Jalankan-Web.cmd**. Biarkan terminal tetap terbuka.
3. Buka http://127.0.0.1:8765/ dan cari nama lokasi, masukkan koordinat, atau pilih titik di peta.

Lingkungan Python lokal ada di folder saudara `RuteSiaga_RUNTIME_LOKAL`, di luar paket yang dikumpulkan. Pada komputer lain, pasang Python 3.14 lalu jalankan `Siapkan-Python.cmd` dari folder final (perlu internet). Kode dan data aplikasi memakai jalur relatif dan tidak membaca proyek lama.

Terminal, dari folder final:
```
.\Jalankan-Terminal.cmd --lat -7.79334345 --lon 110.3666525377634 --scenario pagi --variant akses-awal
```

## Isi folder
- web/: server, antarmuka satu halaman, indeks nama OSM, dan tes web.
- mesin/: UCS/A*, kebijakan jalan, akses awal, CLI, kode persiapan data, dan data graf siap pakai. Folder data tetap dekat mesin untuk menjaga jalur impor/data yang telah diuji.
- hasil/json_manual/: seluruh 7 JSON yang diberikan pengguna, nama dan isinya dipertahankan.
- hasil/json_otomatis/: hasil 80 kasus.
- hasil/json_terminal/: satu contoh hasil terminal; hasil berikutnya ditulis di sini.
- hasil/excel/: Excel hasil 80 kasus.
- pengujian/: skrip untuk mengulang 80 kasus; hasil baru disimpan terpisah.
- dokumen/: rekap final, naskah Bab 3–4 dalam bahasa Indonesia dan Inggris, serta revisi Bab 1–2 dengan perubahan disorot untuk pemeriksaan.
- MANIFEST_SHA256.json: inventaris berkas dan checksum, tidak mencakup lingkungan Python.

Contoh graf sintetis, pencarian jalur berbeda, dokumen versi lama, template kosong, dan hasil duplikat disimpan di folder saudara `RuteSiaga_ARSIP_PENDUKUNG`. Folder arsip dan `RuteSiaga_RUNTIME_LOKAL` tidak perlu dikumpulkan. Peluncur tetap bekerja di komputer ini karena lingkungan Python lokal tetap tersedia di sebelah paket final.

## Batas hasil
Graf OSM/Geofabrik bertanggal 20 September 2026. Tujuan adalah titik jalan RS, bukan pintu IGD. Daftar RS belum dibuktikan lengkap. Biaya adalah estimasi skenario, belum dikalibrasi perjalanan nyata.

Pemetaan penanda ke ruas maksimum 1 km; jarak penanda ke ruas tidak masuk estimasi waktu. Pembatas akses dan arah tetap diperiksa. Jalan terdekat yang terhalang tidak otomatis diganti dengan jalan lain. Penghubung awal yang melonggarkan proksi lebar dibatasi radius 1 km; setelah masuk jaringan utama, aturan lebar tetap berlaku.

80 pengujian otomatis memakai 3 koordinat pengguna dan 17 titik jalan yang dipilih otomatis. Hasilnya memeriksa mesin/model, bukan bukti akses fisik. Excel merupakan snapshot hasil, tidak otomatis berubah setelah menjalankan pengujian baru.

PBF Java mentah tidak disalin (besar); tidak dibutuhkan untuk menjalankan aplikasi. Untuk membangun ulang ekstraksi, sediakan kembali PBF sumber dan periksa parameter skrip persiapan data. Data turunan siap pakai sudah disertakan.

Pemeriksaan paket: 23 tes mesin dan 6 tes web/pencarian lulus. CLI pagi Malioboro Mall menghasilkan 563,6796 detik untuk kedua algoritma. Jalur impor mesin dan paket Python telah diperiksa berasal dari folder final. Kebutuhan eksternal saat menjalankan di komputer ini hanyalah instalasi dasar Python Windows.
