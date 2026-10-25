# Merilis & menguji

## Checklist uji manual di Windows (sebelum tag rilis)
Windows 10 dan 11, idealnya satu bahasa Indonesia dan satu Inggris, laptop dan PC. Catat hasilnya di issue rilis.

**Dasar**
- [ ] `.exe` terbuka tanpa jendela console; splash tampil; jendela dashboard muncul; ikon tray ada
- [ ] Klik dua kali `.exe` lagi atau "Buka dashboard" di tray: jendela yang sudah ada dimunculkan (bukan jendela baru), termasuk saat di-minimize
- [ ] Keluar dari menu tray menghentikan proses (Task Manager bersih)
- [ ] Judul jendela menjadi `(n) Netsys Monitor` saat ada peringatan

**WiFi & jaringan**
- [ ] Tab Jaringan: SSID, band, channel, link rx/tx, sinyal terbaca; cabut WiFi: pesan jelas, bukan error
- [ ] Windows 11 24H2 dengan Layanan Lokasi mati: hint muncul (bila info WiFi kosong)
- [ ] Traceroute ke `1.1.1.1` dan ke domain; tujuan tidak valid ditolak; benchmark DNS menampilkan DNS sistem
- [ ] Penjaga WiFi: pindai pertama = daftar awal; sambungkan HP baru: alert + toast + notifikasi tray; Percayai: alert hilang
- [ ] Pindah ke WiFi lain: daftar baru tanpa banjir alert; kembali: daftar lama dipakai
- [ ] Unduh database vendor: nama pabrikan muncul di daftar perangkat

**Hardware**
- [ ] LibreHardwareMonitor (Admin + Remote Web Server): suhu/fan/daya CPU muncul; kartu GPU menampilkan VRAM/suhu/clock; iGPU+dGPU tampil dua kartu
- [ ] Tutup LibreHardwareMonitor: status "Belum terhubung" dalam sekitar 10 dtk, tanpa error
- [ ] Laptop NVIDIA: pynvml aktif tanpa duplikasi kartu GPU

**Desktop**
- [ ] Auto-start dari tray, restart Windows: start diam-diam di tray; pindahkan `.exe`: status "Lokasi berubah" + tombol Perbarui
- [ ] Jam tenang menahan notifikasi; pesan tes webhook sampai ke Discord/Telegram
- [ ] Tema Gelap: periksa kontras semua tab, grafik, dan dialog (belum pernah dilihat secara visual saat dikembangkan)
- [ ] Catat peringatan antivirus/SmartScreen yang muncul

## Merilis
1. Perbarui `APP_VERSION` di `netsys_monitor/config.py` dan `CHANGELOG.md`.
2. `ruff check . && pytest` hijau; jalankan checklist di atas.
3. `git tag vX.Y.Z && git push --tags`: workflow *Release* membangun `.exe`, installer, dan `SHA256SUMS.txt`, lalu membuat GitHub Release.
4. Isi `GITHUB_REPO` (atau variabel lingkungan `NETSYS_REPO`) di `netsys_monitor/updater.py` agar cek update bekerja.

## Code signing (belum dilakukan)
`.exe` PyInstaller tanpa tanda tangan sering memicu SmartScreen/antivirus. Opsi: sertifikat OV/EV berbayar, atau program
SignPath Foundation untuk proyek open source. Sampai itu ada: sediakan SHA-256 (sudah otomatis), mode `--onedir`, dan kirim
file ke vendor antivirus sebagai *false positive* bila terblokir.
