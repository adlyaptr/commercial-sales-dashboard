# commercial-sales-dashboard
Website Sistem Laporan Commercial

## Role pengguna

- **Admin** login menggunakan akun yang ditentukan oleh `APP_USERNAME` dan `APP_PASSWORD`. Admin dapat melihat seluruh halaman, mengubah data, dan mengelola akun.
- **User** login menggunakan akun yang dibuat Admin. User dapat melihat seluruh halaman dan data, tetapi tidak dapat mengubah atau menghapus data maupun mengelola akun.
- **Divisi** membuka tautan dashboard tanpa login dan hanya dapat melihat Beranda dengan ringkasan agregat.

Beranda (`/` atau `/beranda`) dapat dibuka tanpa login dan tidak menampilkan detail customer atau isi keluhan. Hanya Admin yang dapat membuat akun User, mengganti password, dan menghapus akun pada halaman Pengguna. Akun Divisi lama yang masih tersimpan tidak dapat login; Divisi menggunakan tautan dashboard publik. Kolom role ditambahkan otomatis pada tabel `app_users` saat backend dimulai.

## Issue Management

Halaman Issue (`/issue`) hanya menampilkan data dari Google Sheets yang dikonfigurasi dengan `ISSUE_SHEET_ID` dan `ISSUE_SHEET_GID`. Jika tidak diatur, halaman menggunakan spreadsheet Issue saat ini. Jika spreadsheet tidak dipublikasikan, server membacanya menggunakan Google service account read-only pada `secrets/issue-google-service-account.json`. Aktifkan Google Sheets API pada project service account, bagikan spreadsheet kepada nilai `client_email` pada file kredensial dengan izin Viewer, lalu simpan isi file JSON sebagai GitHub Actions secret `ISSUE_GOOGLE_SERVICE_ACCOUNT_JSON`. Workflow deploy akan mengirim file tersebut ke VM dengan izin file terbatas. Jangan commit atau mengirim file kredensial melalui chat. Ekspor CSV publik tetap digunakan sebagai fallback jika file service account belum dikonfigurasi. Endpoint dashboard hanya tersedia bagi Admin dan User. Data dimuat saat halaman dibuka, dapat diperbarui dengan tombol Sinkronkan Google Sheets, dan disegarkan otomatis setiap lima menit. Cache backend juga berlaku lima menit.

Halaman ini tidak mengubah spreadsheet. Perubahan data dilakukan langsung di Google Sheets. Kolom yang digunakan meliputi Customer (PT), Customer PIC, Terjadinya keluhan, Jenis Keluhan, Root cause, Dampak keluhan, File Pendukung, Tindakan Segera, Update terakhir, Tindakan Corrective, Target Date, dan Status.

## Budget Monitoring

Halaman Budget (`/budget`) membaca target bulanan dari sheet dengan GID `737662524` dan realisasi kategori dari tab `Summary Finance` pada spreadsheet yang sama dengan halaman Issue. Service account read-only yang digunakan untuk Issue harus memiliki izin Viewer pada spreadsheet. Jika service account belum dikonfigurasi, halaman mencoba membaca sheet yang dipublikasikan melalui Google Sheets. Data disinkronkan saat halaman dibuka, dapat diperbarui dengan tombol Sinkronkan Google Sheets, dan disegarkan otomatis setiap lima menit.

Dashboard menampilkan lima kategori operasional pada contoh: Kunjungan Rutin Existing Customer, Meeting Manajemen (HO), Canvassing, Potensial, dan Source. Nilai target bulanan dibaca dari baris rencana kerja `2.1`, `3.1`, `1.3`, `1.1`, dan `1.2`; nilai realisasi dipetakan ke kategori terkait dari tab Summary Finance. Halaman ini hanya menampilkan data dan tidak mengubah spreadsheet.

## Average Price

Perhitungan bulanan menggunakan nilai volume dan hasil dari sheet `AVG` workbook 2026 untuk Januari–November; daftar customer diurutkan mengikuti sheet masing-masing bulan. Nilai impor disimpan sebagai override per customer dan faktor konversi mengikuti nilai presisi pada workbook. Nilai hasil workbook tetap digunakan saat faktor atau kurs diubah selama harga customer tidak berubah. Jika harga customer diubah, total dihitung ulang menggunakan volume dan MMBTU workbook. Total konsolidasi mengikuti sheet `Summary`: KSN Ranca pada Juni dan customer Jawa Timur pada September–November tetap ditampilkan sebagai detail, tetapi tidak masuk total. Untuk rentang tanggal parsial, sistem memakai volume sales aktual agar tidak memakai total satu bulan penuh. Data November 2026 pada workbook berstatus prognosa; detail Desember belum tersedia.

Wilayah customer pada input Average Price dapat dipilih atau diubah oleh pengguna untuk setiap bulan. Wilayah tersebut digunakan untuk pengelompokan subtotal dan perbandingan wilayah.

Baris Average Price dengan nama customer yang sama setelah normalisasi dan operator yang sama ditampilkan sebagai satu baris agregat. Alias OAJ dan PT Optima Adhi Jaya ditampilkan sebagai OPTIMA. Menyimpan customer yang sudah ada memperbarui record terkait, termasuk menyamakan wilayah, tanpa membuat customer baru; seluruh transaksi tetap dipertahankan. Daftar input tidak menampilkan record manual FOB dari master sebagai pilihan terpisah; customer aktif tetap tersedia dari data bulan berjalan.

Jika MMBTU workbook tersedia sebagai override tetapi override USD/Rupiah tidak tersedia, nilai USD dan Rupiah dihitung dari MMBTU workbook tersebut, bukan dari konversi ulang Sm³.

Prognosa target harga memakai volume `Actual + SO` untuk setiap customer berdasarkan volume sales aktual, dengan harga efektif customer dari perhitungan Average Price.
