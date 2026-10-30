# commercial-sales-dashboard
Website Sistem Laporan Commercial

## Role pengguna

- **Admin** login menggunakan akun yang ditentukan oleh `APP_USERNAME` dan `APP_PASSWORD`. Admin dapat melihat seluruh halaman, mengubah data, dan mengelola akun.
- **User** login menggunakan akun yang dibuat Admin. User dapat melihat seluruh halaman dan data, tetapi tidak dapat mengubah atau menghapus data maupun mengelola akun.
- **Divisi** membuka tautan dashboard tanpa login dan hanya dapat melihat Beranda dengan ringkasan agregat.

Beranda (`/` atau `/beranda`) dapat dibuka tanpa login dan tidak menampilkan detail customer atau isi keluhan. Hanya Admin yang dapat membuat akun User, mengganti password, dan menghapus akun pada halaman Pengguna. Akun Divisi lama yang masih tersimpan tidak dapat login; Divisi menggunakan tautan dashboard publik. Kolom role ditambahkan otomatis pada tabel `app_users` saat backend dimulai.

## Issue Management

Halaman Issue (`/issue`) hanya menampilkan data dari Google Sheets yang dikonfigurasi dengan `ISSUE_SHEET_ID` dan `ISSUE_SHEET_GID`. Jika tidak diatur, halaman menggunakan spreadsheet Issue saat ini. Spreadsheet harus dapat dibaca oleh server melalui ekspor CSV Google Sheets; endpoint dashboard hanya tersedia bagi Admin dan User. Data dimuat saat halaman dibuka, dapat diperbarui dengan tombol Sinkronkan Google Sheets, dan disegarkan otomatis setiap lima menit. Cache backend juga berlaku lima menit.

Halaman ini tidak mengubah spreadsheet. Perubahan data dilakukan langsung di Google Sheets. Kolom yang digunakan meliputi Customer (PT), Customer PIC, Terjadinya keluhan, Jenis Keluhan, Root cause, Dampak keluhan, File Pendukung, Tindakan Segera, Update terakhir, Tindakan Corrective, Target Date, dan Status.

## Average Price

Perhitungan bulanan menggunakan nilai volume dan hasil dari sheet `AVG` workbook 2026 untuk Januari–November; daftar customer diurutkan mengikuti sheet masing-masing bulan. Nilai impor disimpan sebagai override per customer dan faktor konversi mengikuti nilai presisi pada workbook. Nilai hasil workbook tetap digunakan saat faktor atau kurs diubah selama harga customer tidak berubah. Jika harga customer diubah, total dihitung ulang menggunakan volume dan MMBTU workbook. Total konsolidasi mengikuti sheet `Summary`: KSN Ranca pada Juni dan customer Jawa Timur pada September–November tetap ditampilkan sebagai detail, tetapi tidak masuk total. Untuk rentang tanggal parsial, sistem memakai volume sales aktual agar tidak memakai total satu bulan penuh. Data November 2026 pada workbook berstatus prognosa; detail Desember belum tersedia.

Wilayah customer pada input Average Price dapat dipilih atau diubah oleh pengguna untuk setiap bulan. Wilayah tersebut digunakan untuk pengelompokan subtotal dan perbandingan wilayah.

Baris Average Price dengan nama customer yang sama setelah normalisasi dan operator yang sama ditampilkan sebagai satu baris agregat. Alias OAJ dan PT Optima Adhi Jaya ditampilkan sebagai OPTIMA. Menyimpan customer yang sudah ada memperbarui record terkait, termasuk menyamakan wilayah, tanpa membuat customer baru; seluruh transaksi tetap dipertahankan. Daftar input tidak menampilkan record manual FOB dari master sebagai pilihan terpisah; customer aktif tetap tersedia dari data bulan berjalan.

Jika MMBTU workbook tersedia sebagai override tetapi override USD/Rupiah tidak tersedia, nilai USD dan Rupiah dihitung dari MMBTU workbook tersebut, bukan dari konversi ulang Sm³.

Prognosa target harga memakai volume `Actual + SO` untuk setiap customer berdasarkan volume sales aktual, dengan harga efektif customer dari perhitungan Average Price.
