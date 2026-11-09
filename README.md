# commercial-sales-dashboard
Website Sistem Laporan Commercial

## Role pengguna

- **Admin** login menggunakan akun yang ditentukan oleh `APP_USERNAME` dan `APP_PASSWORD`. Admin dapat melihat seluruh halaman, termasuk Average Price, mengubah data, dan mengelola akun.
- **User** login menggunakan akun yang dibuat Admin. User dapat melihat seluruh halaman dan data, termasuk Average Price, tetapi tidak dapat mengubah atau menghapus data maupun mengelola akun.
- **Divisi** membuka tautan dashboard tanpa login dan dapat melihat seluruh ringkasan agregat di Beranda, termasuk Average Price, volume per wilayah, dan ringkasan complain. Detail customer dan isi keluhan tidak ditampilkan.

Beranda (`/` atau `/beranda`) dapat dibuka tanpa login dan tidak menampilkan detail customer atau isi keluhan. Hanya Admin yang dapat membuat akun User, mengganti password, dan menghapus akun pada halaman Pengguna. Role SPH untuk akun Admin/User diatur Admin melalui tab **Akses pengguna** pada aplikasi SPH CNG Reethau. Akun Divisi lama yang masih tersimpan tidak dapat login; Divisi menggunakan tautan dashboard publik. Kolom role ditambahkan otomatis pada tabel `app_users` saat backend dimulai.

## SPH CNG Reethau

Halaman login menyediakan pilihan **Commercial Monitoring** atau **SPH CNG Reethau**. Admin dapat membuka SPH; akun User hanya dapat memilihnya jika Admin menetapkan role Sales, Commercial Head, atau Legal. Role yang ditetapkan pada akun menjadi satu-satunya sumber otorisasi tindakan workflow dan tidak dapat dipilih ulang dari halaman SPH. Admin tanpa role proses memiliki akses lihat saja.

SPH memakai tabel MySQL `sph_customers`, `sph_sequences`, `sph_proposals`, dan `sph_proposal_logs`, yang dibuat saat backend menginisialisasi skema. Basis data baru dimulai tanpa proposal atau pelanggan contoh. Draft yang disimpan mendapatkan nomor SPH berurutan per bulan dan semua transisi workflow dicatat dengan aktor, role, waktu, serta keterangan. Semua penawaran hanya memerlukan satu persetujuan dari Commercial Head. Draft yang sebelumnya sudah mendapat persetujuan Commercial Head dan masih menunggu persetujuan Direksi akan ditandai disetujui saat backend dimulai. SPH dapat diedit oleh Sales pada semua status kecuali Aktif; perubahan pada SPH yang sudah dikirim membuat versi baru, menghapus persetujuan sebelumnya, dan mengembalikannya ke Draft untuk diajukan ulang. PDF mengikuti susunan surat contoh, mencakup kondisi dan detail penawaran, kewajiban, ketentuan lain, penutup, dan tanda tangan Commercial Head. Draft memakai watermark Draft. Generator PDF menggunakan ReportLab yang terpasang dari `backend/requirements.txt`.

Editor SPH menyediakan daftar ceklis kewajiban Reethau dan Customer. Opsi **Lainnya** membuka kolom esai untuk mencatat kewajiban tambahan; kewajiban yang dipilih dan catatan tambahan disimpan bersama draft dan ditampilkan pada PDF SPH.

## Issue Management

Halaman Issue (`/issue`) hanya menampilkan data dari Google Sheets yang dikonfigurasi dengan `ISSUE_SHEET_ID` dan `ISSUE_SHEET_GID`. Jika tidak diatur, halaman menggunakan spreadsheet Issue saat ini. Jika spreadsheet tidak dipublikasikan, server membacanya menggunakan Google service account read-only pada `secrets/issue-google-service-account.json`. Aktifkan Google Sheets API pada project service account, bagikan spreadsheet kepada nilai `client_email` pada file kredensial dengan izin Viewer, lalu simpan isi file JSON sebagai GitHub Actions secret `ISSUE_GOOGLE_SERVICE_ACCOUNT_JSON`. Workflow deploy akan mengirim file tersebut ke VM dengan izin file terbatas. Jangan commit atau mengirim file kredensial melalui chat. Ekspor CSV publik tetap digunakan sebagai fallback jika file service account belum dikonfigurasi. Endpoint dashboard hanya tersedia bagi Admin dan User. Data dimuat otomatis saat halaman dibuka dan disegarkan setiap lima menit. Cache backend juga berlaku lima menit.

Halaman ini tidak mengubah spreadsheet. Perubahan data dilakukan langsung di Google Sheets. Kolom yang digunakan meliputi Customer (PT), Customer PIC, Terjadinya keluhan, Jenis Keluhan, Root cause, Dampak keluhan, File Pendukung, Tindakan Segera, Update terakhir, Tindakan Corrective, Target Date, dan Status.

## Prognosa Sales Order Harian

Tabel Harian membaca rencana per customer dari tab `SO` pada spreadsheet Volume CNG 2026 (`SALES_ORDER_SHEET_ID` dan `SALES_ORDER_SHEET_GID`, default GID `694583576`). Sheet dibaca dari endpoint Google Visualization publik menggunakan nilai mentah agar pecahan angka tidak dibulatkan oleh format tampilan, lalu disegarkan setiap lima menit. Nama customer dicocokkan dengan master customer; nama dengan nilai SO yang belum cocok ditampilkan sebagai peringatan.

Nilai SO dari sheet menjadi SO di tabel Harian. Actual non-zero yang sudah diimpor tetap digunakan. Jika satu tanggal belum memiliki Actual non-zero, nilai Actual 0 pada tanggal tersebut mengikuti SO sebagai prognosa dan diberi penanda `P`. Pastikan sheet dapat dibaca secara publik agar backend dapat mengakses datanya.

Saat halaman Harian terbuka, data dashboard dan rentang tanggal diperbarui otomatis setiap sekitar lima menit (selama tab browser aktif), mengikuti cache sheet SO lima menit. Perubahan spreadsheet mungkin memerlukan waktu hingga satu siklus refresh untuk tampil.

Total Actual pada Beranda hanya memakai Actual dari data harian yang sudah diimpor; prognosa SO tidak ditambahkan. Ringkasan Harian tetap memakai Actual impor dan mengisi SO sebagai prognosa untuk tanggal/customer yang belum memiliki Actual impor, tanpa menimpa Actual impor. Volume per wilayah di Beranda mengelompokkan seluruh Actual impor berdasarkan MS: SETU/KHT ke JABAR, BLORA ke JATENG, dan WUNUT ke JATIM. Customer KTN mengikuti wilayah JATENG pada Target 2026. Karena semua baris Actual teralokasi ke salah satu MS, jumlah ketiga wilayah sama dengan Total Actual pada rentang yang sama.

Pada halaman Harian tersedia tombol **Export Excel Bulanan**. File mengikuti workbook template di `backend/templates/monthly_sales_template.xlsx`, termasuk seluruh sheet dan header; data penjualan diisi untuk bulan pada tanggal laporan yang dipilih.

## Budget Monitoring

Halaman Budget (`/budget`) membaca target bulanan dari sheet dengan GID `737662524` dan realisasi kategori dari tab `Summary Finance` pada spreadsheet yang sama dengan halaman Issue. Service account read-only yang digunakan untuk Issue harus memiliki izin Viewer pada spreadsheet. Jika service account belum dikonfigurasi, halaman mencoba membaca sheet yang dipublikasikan melalui Google Sheets. Data dimuat otomatis saat halaman dibuka dan disegarkan setiap lima menit.

Dashboard menampilkan lima kategori operasional pada contoh: Kunjungan Rutin Existing Customer, Meeting Manajemen (HO), Canvassing, Potensial, dan Source. Nilai target bulanan dibaca dari baris rencana kerja `2.1`, `3.1`, `1.3`, `1.1`, dan `1.2`; nilai realisasi dipetakan ke kategori terkait dari tab Summary Finance. Halaman ini hanya menampilkan data dan tidak mengubah spreadsheet.

## Average Price

Average Price tersedia di Beranda publik hanya dalam bentuk agregat tanpa detail customer; User dapat melihat detail Average Price dan halaman Average Price, tetapi tidak dapat mengubah data. Hanya Admin yang dapat mengedit Average Price. Pada halaman Average Price, Admin dapat mengunggah workbook melalui **Impor Excel Average Price**. Impor membaca hasil formula tersimpan pada sheet `AVG` Januari–November, memperbarui nilai bulanan yang tersedia, dan menyimpan ringkasan ASP/total dari workbook. Data yang diimpor menjadi acuan bulan tersebut; sinkronisasi Google Sheet dan input harga manual tidak menimpa data bulan yang sudah diimpor. Sebelum mengunggah, buka dan simpan ulang workbook di Excel agar nilai formula dan tautan workbook sudah diperbarui. Unggah ulang workbook setiap kali ingin memperbarui angka. Customer di workbook harus sudah cocok dengan master customer; impor ditolak jika masih ada customer yang belum cocok. Desember belum tersedia.

Untuk bulan yang belum memakai workbook sebagai acuan, halaman Admin menyinkronkan harga dari tab `Harga Customer 2026` saat dibuka atau bulan diganti, lalu setiap lima menit selama halaman tetap terbuka. Harga bertanda `$` dimasukkan sebagai USD/MMBTU dan harga bertanda `Rp` sebagai Rp/Sm³. Nilai kosong atau `off` menonaktifkan harga bulan tersebut. Jika ditemukan customer baru, Admin diminta memilih operator dan wilayah sebelum customer serta harganya ditambahkan. Integrasi mengutamakan Google Sheets API dengan service account read-only yang sama dengan halaman Issue: aktifkan Google Sheets API, bagikan spreadsheet kepada `client_email` service account dengan izin **Viewer**, dan sediakan kredensial pada server. Untuk lokal tanpa Docker, letakkan file JSON sebagai `secrets/issue-google-service-account.json` di root repository; path ini diabaikan Git. Untuk Docker Compose, file yang sama dipasang read-only ke container. Untuk deploy GitHub Actions, simpan seluruh JSON sebagai secret `ISSUE_GOOGLE_SERVICE_ACCOUNT_JSON`; deploy branch `prod` akan mengirimnya ke server. Izin **Editor** tidak diperlukan. Jika service account tidak dikonfigurasi, server mencoba ekspor CSV yang hanya berfungsi untuk spreadsheet dengan akses baca publik. Jangan memberi akses Editor secara publik dan jangan commit atau mengirim file kredensial. Spreadsheet ID, tab GID, dan nama tab dapat diubah melalui `AVERAGE_PRICE_SHEET_ID`, `AVERAGE_PRICE_SHEET_GID`, dan `AVERAGE_PRICE_SHEET_TITLE`.

Wilayah customer pada input Average Price dapat dipilih atau diubah oleh pengguna untuk setiap bulan. Wilayah tersebut digunakan untuk pengelompokan subtotal dan perbandingan wilayah.

Baris Average Price dengan nama customer yang sama setelah normalisasi dan operator yang sama ditampilkan sebagai satu baris agregat. Alias OAJ dan PT Optima Adhi Jaya ditampilkan sebagai OPTIMA. Menyimpan customer yang sudah ada memperbarui record terkait, termasuk menyamakan wilayah, tanpa membuat customer baru; seluruh transaksi tetap dipertahankan. Daftar input tidak menampilkan record manual FOB dari master sebagai pilihan terpisah; customer aktif tetap tersedia dari data bulan berjalan.

Jika MMBTU workbook tersedia sebagai override tetapi override USD/Rupiah tidak tersedia, nilai USD dan Rupiah dihitung dari MMBTU workbook tersebut, bukan dari konversi ulang Sm³.

Prognosa target harga memakai volume `Actual + SO` untuk setiap customer berdasarkan volume sales aktual, dengan harga efektif customer dari perhitungan Average Price.
