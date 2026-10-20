# commercial-sales-dashboard
Website Sistem Laporan Commercial

## Role pengguna

Sistem menyediakan dua role:

- **Admin** menggunakan akun yang ditentukan oleh `APP_USERNAME` dan `APP_PASSWORD` pada konfigurasi backend, serta dapat membuka seluruh halaman.
- **Divisi** hanya dapat membuka Beranda. Admin dapat membuat akun divisi, mengganti kata sandi, dan menghapus akun melalui menu **Pengguna**.

Kolom role ditambahkan otomatis pada tabel `app_users` saat backend dimulai. Buat akun divisi melalui halaman Pengguna; kata sandi akun baru harus memiliki minimal 12 karakter.

## Average Price

Perhitungan bulanan menggunakan nilai volume dan total dari sheet `AVG` workbook 2026 untuk Januari–November; nilai impor disimpan sebagai override per customer. Total konsolidasi mengikuti sheet `Summary`: KSN Ranca pada Juni dan customer Jawa Timur pada September–November tetap ditampilkan sebagai detail, tetapi tidak masuk total. Untuk rentang tanggal parsial, sistem memakai volume sales aktual agar tidak memakai total satu bulan penuh. Data November 2026 pada workbook berstatus prognosa; detail Desember belum tersedia.
