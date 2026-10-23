# commercial-sales-dashboard
Website Sistem Laporan Commercial

## Role pengguna

Beranda dapat dibuka tanpa login dan menampilkan ringkasan penjualan, agregat wilayah, jumlah customer dengan harga valid, serta tanggal dan status keluhan. Data customer dan rincian keluhan tidak ditampilkan kepada pengunjung publik.

Sistem menyediakan dua role:

- **Admin** menggunakan akun yang ditentukan oleh `APP_USERNAME` dan `APP_PASSWORD` pada konfigurasi backend, serta dapat membuka seluruh halaman.
- **Divisi** harus login dan hanya dapat membuka Beranda. Admin dapat membuat akun divisi, mengganti kata sandi, dan menghapus akun melalui menu **Pengguna**.

Halaman selain Beranda memerlukan login Admin. Karena Beranda bersifat publik, siapa pun yang mengakses alamat sistem dapat melihat ringkasan yang tersedia di sana.

Kolom role ditambahkan otomatis pada tabel `app_users` saat backend dimulai. Buat akun divisi melalui halaman Pengguna; kata sandi akun baru harus memiliki minimal 12 karakter.

## Average Price

Perhitungan bulanan menggunakan nilai volume dan hasil dari sheet `AVG` workbook 2026 untuk Januari–November; daftar customer diurutkan mengikuti sheet masing-masing bulan. Nilai impor disimpan sebagai override per customer dan faktor konversi mengikuti nilai presisi pada workbook. Nilai hasil workbook tetap digunakan saat faktor atau kurs diubah selama harga customer tidak berubah. Jika harga customer diubah, total dihitung ulang menggunakan volume dan MMBTU workbook. Total konsolidasi mengikuti sheet `Summary`: KSN Ranca pada Juni dan customer Jawa Timur pada September–November tetap ditampilkan sebagai detail, tetapi tidak masuk total. Untuk rentang tanggal parsial, sistem memakai volume sales aktual agar tidak memakai total satu bulan penuh. Data November 2026 pada workbook berstatus prognosa; detail Desember belum tersedia.

Wilayah customer pada input Average Price dapat dipilih atau diubah oleh pengguna untuk setiap bulan. Wilayah tersebut digunakan untuk pengelompokan subtotal dan perbandingan wilayah.

Baris Average Price dengan nama customer yang sama setelah normalisasi dan operator yang sama ditampilkan sebagai satu baris agregat. Alias OAJ dan PT Optima Adhi Jaya ditampilkan sebagai OPTIMA. Menyimpan customer yang sudah ada memperbarui record terkait, termasuk menyamakan wilayah, tanpa membuat customer baru; seluruh transaksi tetap dipertahankan. Daftar input tidak menampilkan record manual FOB dari master sebagai pilihan terpisah; customer aktif tetap tersedia dari data bulan berjalan.

Jika MMBTU workbook tersedia sebagai override tetapi override USD/Rupiah tidak tersedia, nilai USD dan Rupiah dihitung dari MMBTU workbook tersebut, bukan dari konversi ulang Sm³.

Prognosa target harga memakai volume `Actual + SO` untuk setiap customer berdasarkan volume sales aktual, dengan harga efektif customer dari perhitungan Average Price.
